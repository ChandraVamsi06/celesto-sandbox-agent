-- Schema definition for Run Ledger
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(255) PRIMARY KEY,
    sandbox_name VARCHAR(255) NOT NULL,
    problem_id VARCHAR(255) NOT NULL,
    state VARCHAR(50) NOT NULL,
    execution_target VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Idempotent seed insertion: sbx-seeddemo1 in state deleted with execution_target celesto_sandbox
INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
VALUES ('run-seed-001', 'sbx-seeddemo1', 'prob-seed-001', 'deleted', 'celesto_sandbox')
ON CONFLICT (run_id) DO UPDATE SET
    sandbox_name = EXCLUDED.sandbox_name,
    problem_id = EXCLUDED.problem_id,
    state = EXCLUDED.state,
    execution_target = EXCLUDED.execution_target;
