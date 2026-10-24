import re
import json
import math
import yaml
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
ALLOWED_CAPABILITY_IDS = {
    "persistence", "snapshots", "celestofs", "browser", "published_ports",
    "network_policy", "safety_hooks", "host_mounts", "coding_agent_preset",
    "agentor_durable",
}


def test_docker_compose_and_dockerfile():
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists(), "docker-compose.yml must exist at root"
    
    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)
        
    services = compose.get("services", {})
    assert "api" in services, "service 'api' must be defined in docker-compose.yml"
    assert "ledger" in services, "service 'ledger' must be defined in docker-compose.yml"
    
    # Check api healthcheck
    api = services["api"]
    assert "healthcheck" in api, "api must have a healthcheck"
    api_hc = api["healthcheck"]
    for field in ["interval", "timeout", "retries", "start_period"]:
        assert field in api_hc, f"api healthcheck missing '{field}'"
        
    # Check ledger healthcheck
    ledger = services["ledger"]
    assert "healthcheck" in ledger, "ledger must have a healthcheck"
    ledger_hc = ledger["healthcheck"]
    for field in ["interval", "timeout", "retries", "start_period"]:
        assert field in ledger_hc, f"ledger healthcheck missing '{field}'"
    assert any("pg_isready" in str(cmd) for cmd in ledger_hc.get("test", [])), "ledger healthcheck must use pg_isready"

    # Check ledger seeds volume mount
    volumes = ledger.get("volumes", [])
    assert any("./seeds" in str(v) for v in volumes), "ledger must mount ./seeds init volume"

    # Check root Dockerfile
    assert Path("Dockerfile").exists(), "Dockerfile must exist at root"


def test_env_example_and_no_live_env():
    env_example_path = Path(".env.example")
    assert env_example_path.exists(), ".env.example must exist"
    
    # Must NOT have .env committed
    assert not Path(".env").exists(), ".env must NOT be present in root submission"
    
    content = env_example_path.read_text(encoding="utf-8")
    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT",
    ]
    for key in required_keys:
        assert f"{key}=" in content, f".env.example must contain key '{key}'"
        
    # Check placeholders
    assert "replace-me" in content or "replace" in content.lower(), "Values must be placeholders"


def test_seeds_sql():
    seed_path = Path("seeds/01_runs.sql")
    assert seed_path.exists(), "seeds/01_runs.sql must exist"
    content = seed_path.read_text(encoding="utf-8")
    assert "sbx-seeddemo1" in content, "Seed must specify sandbox name 'sbx-seeddemo1'"
    assert "deleted" in content, "Seed state must be 'deleted'"
    assert "celesto_sandbox" in content, "Seed execution_target must be 'celesto_sandbox'"


def test_problem_report():
    path = Path("reports/problem.json")
    assert path.exists(), "reports/problem.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    for key in ["who", "agent_work", "proof_output", "idea_source"]:
        assert key in data, f"reports/problem.json missing key '{key}'"
        
    assert data["idea_source"] in ["idea_bank", "original"]
    assert len(data["who"]) >= 40, "who must be at least 40 characters"
    assert len(data["agent_work"]) >= 40, "agent_work must be at least 40 characters"
    assert len(data["proof_output"]) >= 20, "proof_output must be at least 20 characters"


def test_capabilities_report():
    path = Path("reports/capabilities.json")
    assert path.exists(), "reports/capabilities.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    caps = data.get("capabilities", [])
    assert len(caps) >= 2, "capabilities must have at least 2 objects"
    
    seen_ids = set()
    for cap in caps:
        cap_id = cap.get("id")
        assert cap_id in ALLOWED_CAPABILITY_IDS, f"Invalid capability id '{cap_id}'"
        assert cap_id not in seen_ids, f"Duplicate capability id '{cap_id}'"
        seen_ids.add(cap_id)
        
        why = cap.get("why", "")
        assert len(why) >= 80, f"why field for '{cap_id}' must be at least 80 characters"
        
        ev_path = Path(cap.get("evidence_path", ""))
        assert ev_path.exists(), f"evidence_path '{ev_path}' does not exist in repo"


def test_lifecycle_report():
    path = Path("reports/lifecycle.json")
    assert path.exists(), "reports/lifecycle.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    assert data.get("cleanup_on_success") is True
    assert data.get("cleanup_on_failure") is True
    assert data.get("cleanup_on_interrupt") is True
    
    names = data.get("sandbox_names", [])
    assert len(names) > 0, "sandbox_names must be non-empty"
    assert len(names) == len(set(names)), "sandbox_names must be unique"
    
    # Cross reference with logs/commands.jsonl or reliability.json
    commands_names = set()
    cmd_path = Path("logs/commands.jsonl")
    if cmd_path.exists():
        for line in cmd_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                commands_names.add(json.loads(line).get("sandbox_name"))
                
    rel_names = set()
    rel_path = Path("reports/reliability.json")
    if rel_path.exists():
        rel_data = json.loads(rel_path.read_text(encoding="utf-8"))
        for r in rel_data.get("runs", []):
            rel_names.add(r.get("sandbox_name"))
            
    for name in names:
        assert SANDBOX_REGEX.match(name), f"Invalid sandbox name '{name}'"
        assert (name in commands_names) or (name in rel_names), f"Sandbox '{name}' not found in commands.jsonl or reliability.json"


def test_commands_log():
    path = Path("logs/commands.jsonl")
    assert path.exists(), "logs/commands.jsonl must exist"
    lines = [line.strip() for line in path.read_text(encoding="utf-8").strip().split("\n") if line.strip()]
    assert len(lines) >= 1, "logs/commands.jsonl must have at least one line"
    
    decisions = set()
    for line in lines:
        record = json.loads(line)
        assert "ts" in record
        assert SANDBOX_REGEX.match(record.get("sandbox_name", ""))
        assert len(record.get("command", "")) > 0
        assert record.get("decision") in ["allow", "block"]
        assert record.get("execution_target") == "celesto_sandbox", "execution_target must strictly be 'celesto_sandbox'"
        decisions.add(record.get("decision"))
        
    assert "allow" in decisions
    assert "block" in decisions


def test_reliability_report_and_postmortem():
    path = Path("reports/reliability.json")
    assert path.exists(), "reports/reliability.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    runs = data.get("runs", [])
    run_count = data.get("run_count")
    assert run_count >= 20, "run_count must be at least 20"
    assert len(runs) == run_count, "run_count must equal len(runs)"
    
    seen_names = set()
    for r in runs:
        s_name = r.get("sandbox_name")
        assert SANDBOX_REGEX.match(s_name), f"Invalid sandbox_name '{s_name}'"
        assert s_name not in seen_names, f"Duplicate sandbox_name '{s_name}'"
        seen_names.add(s_name)
        assert r.get("fresh") is True
        assert isinstance(r.get("success"), bool)
        assert r.get("wall_clock_s") >= 0
        assert r.get("boot_to_ready_s") >= 0
        assert r.get("cost_usd") >= 0
        
    # Verify exact arithmetic
    calc_success_rate = sum(1 for r in runs if r["success"]) / run_count
    assert abs(data["success_rate"] - calc_success_rate) <= 0.001
    
    sorted_wall = sorted([r["wall_clock_s"] for r in runs])
    calc_median_wall = (sorted_wall[9] + sorted_wall[10]) / 2.0
    assert abs(data["median_wall_clock_s"] - calc_median_wall) <= 0.001
    
    calc_p90_wall = sorted_wall[math.ceil(0.90 * run_count) - 1]
    assert abs(data["p90_wall_clock_s"] - calc_p90_wall) <= 0.001
    
    sorted_boot = sorted([r["boot_to_ready_s"] for r in runs])
    calc_median_boot = (sorted_boot[9] + sorted_boot[10]) / 2.0
    assert abs(data["median_boot_to_ready_s"] - calc_median_boot) <= 0.001
    
    calc_total_cost = sum(r["cost_usd"] for r in runs)
    assert abs(data["total_cost_usd"] - calc_total_cost) <= 0.01
    
    # Check postmortem
    pm_path = Path(data.get("postmortem_path", ""))
    assert pm_path.exists(), f"postmortem file '{pm_path}' must exist"
    assert len(pm_path.read_text(encoding="utf-8")) >= 200, "postmortem must be at least 200 characters"


def test_containment_report():
    path = Path("reports/containment.json")
    assert path.exists(), "reports/containment.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    assert data.get("attack") in ["prompt_injection_exfil", "destructive_command", "suspicious_package"]
    assert data.get("blocked") is True
    assert data.get("host_untouched") is True
    
    ev_paths = data.get("evidence_paths", [])
    assert len(ev_paths) >= 1
    for ep in ev_paths:
        assert Path(ep).exists(), f"evidence path '{ep}' must exist"


def test_failure_policy_report_and_trace():
    path = Path("reports/failure_policy.json")
    assert path.exists(), "reports/failure_policy.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    assert data.get("failed_step") == 7
    assert data.get("total_steps") == 10
    policy = data.get("policy")
    assert policy in ["resume", "rollback", "fresh"]
    assert len(data.get("rationale", "")) >= 200
    
    trace_path = Path(data.get("trace_path", ""))
    assert trace_path.exists(), f"trace_path '{trace_path}' must exist"
    
    trace_lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").strip().split("\n") if line.strip()]
    has_policy_applied = any(
        t.get("event") == "policy_applied" and t.get("policy") == policy
        for t in trace_lines
    )
    assert has_policy_applied, f"failure trace must contain event 'policy_applied' with policy '{policy}'"


def test_concurrency_report():
    path = Path("reports/concurrency.json")
    assert path.exists(), "reports/concurrency.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    
    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "concurrency report must list at least 5 jobs"
    
    seen = set()
    for job in jobs:
        s_name = job.get("sandbox_name")
        assert SANDBOX_REGEX.match(s_name), f"Invalid sandbox_name '{s_name}'"
        assert s_name not in seen, f"Duplicate sandbox name '{s_name}'"
        seen.add(s_name)
        assert len(job.get("started_at", "")) > 0
        
    assert len(data.get("breakage_notes", "")) >= 40, "breakage_notes must be at least 40 characters"


def test_readme_required_phrases():
    readme_path = Path("README.md")
    assert readme_path.exists(), "README.md must exist at root"
    content = readme_path.read_text(encoding="utf-8")
    
    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup",
    ]
    for phrase in required_phrases:
        assert phrase in content, f"README.md missing required phrase '{phrase}'"


def test_api_endpoints():
    client = TestClient(app)
    
    # 1. Health endpoint
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}
    
    # 2. Get runs (must include sbx-seeddemo1)
    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert any(r.get("sandbox_name") == "sbx-seeddemo1" for r in runs), "runs must include sbx-seeddemo1"
    
    # 3. Post valid run
    valid_payload = {
        "run_id": "test-run-101",
        "sandbox_name": "sbx-testrun01",
        "problem_id": "prob-test-01",
        "state": "running",
        "execution_target": "celesto_sandbox",
    }
    res_post = client.post("/api/runs", json=valid_payload)
    assert res_post.status_code == 201
    data = res_post.json()
    assert data["sandbox_name"] == "sbx-testrun01"
    
    # 4. Post invalid execution_target (host) -> 400
    bad_target = {**valid_payload, "run_id": "test-bad-target", "execution_target": "host"}
    res_bad_target = client.post("/api/runs", json=bad_target)
    assert res_bad_target.status_code == 400
    
    # 5. Post invalid state -> 400
    bad_state = {**valid_payload, "run_id": "test-bad-state", "state": "unknown_state"}
    res_bad_state = client.post("/api/runs", json=bad_state)
    assert res_bad_state.status_code == 400
    
    # 6. Post invalid sandbox_name -> 400
    bad_sbx = {**valid_payload, "run_id": "test-bad-sbx", "sandbox_name": "invalid-name"}
    res_bad_sbx = client.post("/api/runs", json=bad_sbx)
    assert res_bad_sbx.status_code == 400


def test_reports_served():
    client = TestClient(app)
    res_problem = client.get("/reports/problem.json")
    assert res_problem.status_code == 200
    assert "who" in res_problem.json()

    res_capabilities = client.get("/reports/capabilities.json")
    assert res_capabilities.status_code == 200
    assert "capabilities" in res_capabilities.json()

    res_postmortem = client.get("/reports/postmortem.md")
    assert res_postmortem.status_code == 200
    assert len(res_postmortem.text) >= 200

