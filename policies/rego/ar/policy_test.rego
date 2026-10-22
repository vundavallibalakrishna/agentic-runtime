package ar.policy_test

import rego.v1

import data.ar.policy

fixture := {
	"tool": {"qualified_name": "petstore.create_pet", "name": "create_pet", "server_slug": "petstore", "risk_class": "W2"},
	"agent": {"id": "a", "slug": "desk", "overrides": {}},
	"run": {"id": "r", "trigger": "chat", "channel": "web"},
	"user": {"id": "u", "groups": [], "teams": []},
	"args": {"body": {"name": "Fido"}},
	"settings": {"approvals": {"default_ttl_s": 86400}, "security": {"require_step_up_for_w3": true}},
}

test_w2_default if {
	policy.decision == {"decision": "require_approval", "reasons": ["writes that affect others wait for approval"], "matched_rule_ids": [], "approval": {"approvers": {"mode": "requester", "groups": [], "users": []}, "required_approvals": 1, "four_eyes": false, "step_up": false, "ttl_s": 86400, "message": ""}} with input as object.union(fixture, {"rules": []})
}

test_deny_wins if {
	result := policy.decision with input as object.union(fixture, {"rules": [{"id": "d", "effect": "deny", "message": "no pets", "match": {"tools": ["petstore.create_pet"]}}]})
	result.decision == "deny"
	result.reasons == ["no pets"]
}

test_read_allows if {
	sample := object.union(fixture, {"tool": {"qualified_name": "warehouse.run_query", "name": "run_query", "server_slug": "warehouse", "risk_class": "R0"}, "rules": []})
	policy.decision.decision == "allow" with input as sample
}

test_w3_denies if {
	sample := object.union(fixture, {"tool": {"qualified_name": "petstore.delete_pet", "name": "delete_pet", "server_slug": "petstore", "risk_class": "W3"}, "rules": []})
	policy.decision.decision == "deny" with input as sample
}

test_arg_eq if {
	result := policy.decision with input as object.union(fixture, {"rules": [{"id": "n", "effect": "deny", "message": "that name", "match": {"args": [{"path": "$.body.name", "op": "eq", "value": "Fido"}]}}]})
	result.decision == "deny"
}

test_allow_rule if {
	result := policy.decision with input as object.union(fixture, {"rules": [{"id": "a", "effect": "allow", "match": {"tools": ["petstore.*"]}}]})
	result.decision == "allow"
}

test_w3_allow_needs_approval if {
	sample := object.union(fixture, {"tool": {"qualified_name": "petstore.delete_pet", "name": "delete_pet", "server_slug": "petstore", "risk_class": "W3"}, "rules": [{"id": "a", "effect": "allow", "match": {"servers": ["petstore"], "riskClasses": ["W3"], "agents": ["desk"], "triggers": ["chat"], "channels": ["web"]}}]})
	result := policy.decision with input as sample
	result.decision == "require_approval"
	result.approval.four_eyes == true
	result.approval.approvers.mode == "agent_owner"
}

test_groups_and_exists if {
	sample := object.union(fixture, {"user": {"id": "u", "groups": ["ops"], "teams": ["desk"]}, "rules": [{"id": "g", "effect": "deny", "message": "ops", "match": {"userGroups": ["ops"], "user_teams": ["desk"], "args": [{"path": "$.body.name", "op": "exists"}]}}]})
	policy.decision.decision == "deny" with input as sample
}

test_glob_star if {
	result := policy.decision with input as object.union(fixture, {"rules": [{"id": "s", "effect": "deny", "message": "any", "match": {"tools": ["*"]}}]})
	result.decision == "deny"
}

test_override if {
	sample := object.union(fixture, {"tool": {"qualified_name": "warehouse.run_query", "name": "run_query", "server_slug": "warehouse", "risk_class": "R1"}, "agent": {"id": "a", "slug": "desk", "overrides": {"run_query": {"require_approval": "always"}}}, "rules": []})
	result := policy.decision with input as sample
	result.decision == "require_approval"
}

test_w1_allows if {
	sample := object.union(fixture, {"tool": {"qualified_name": "files.read", "name": "read", "server_slug": "files", "risk_class": "W1"}, "rules": []})
	policy.decision.decision == "allow" with input as sample
}

test_w3_require_keeps_named_approvers if {
	sample := object.union(fixture, {"tool": {"qualified_name": "petstore.delete_pet", "name": "delete_pet", "server_slug": "petstore", "risk_class": "W3"}, "rules": [{"id": "r", "effect": "require_approval", "message": "confirm the delete", "approval": {"approvers": {"mode": "users", "groups": [], "users": ["approver"]}}, "match": {"tools": ["petstore.delete_pet"]}}]})
	result := policy.decision with input as sample
	result.decision == "require_approval"
	result.approval.four_eyes == true
	result.approval.step_up == true
	result.approval.approvers.mode == "users"
	result.approval.approvers.users == ["approver"]
}

test_require_rule if {
	result := policy.decision with input as object.union(fixture, {"rules": [{"id": "r", "effect": "require_approval", "message": "ask", "approval": {"approvers": {"mode": "agent_owner", "groups": ["g"], "users": ["u"]}, "required_approvals": 2, "four_eyes": true, "step_up": true, "ttl_s": 120}, "match": {"tools": ["petstore.create_pet"]}}]})
	result.decision == "require_approval"
	result.approval.required_approvals == 2
	result.approval.step_up == true
}

test_bundle_rules if {
	call := {"tenant_id": "t", "tool": fixture.tool, "agent": fixture.agent, "run": fixture.run, "user": fixture.user, "args": fixture.args, "settings": fixture.settings}
	result := policy.decision with input as call with data.tenants as {"t": {"rules": [{"id": "d", "effect": "deny", "message": "bundled", "match": {}}]}}
	result.decision == "deny"
	result.reasons == ["bundled"]
}
