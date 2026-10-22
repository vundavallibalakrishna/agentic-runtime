package ar.policy

import rego.v1

import data.ar.jsonpath

decision := combine(object.get(input, "rules", []), settings) if {
	object.get(input, "rules", null) != null
	settings := object.get(input, "settings", {
		"approvals": {"default_ttl_s": 86400},
		"security": {"require_step_up_for_w3": true},
	})
}

decision := combine(object.get(tenant, "rules", []), settings) if {
	not input.rules
	tenant := object.get(data.tenants, object.get(input, "tenant_id", ""), {})
	settings := object.get(input, "settings", {
		"approvals": {"default_ttl_s": 86400},
		"security": {"require_step_up_for_w3": true},
	})
}

default decision := {
	"decision": "deny",
	"reasons": ["policy_unavailable"],
	"matched_rule_ids": [],
	"approval": null,
}

combine(rules, _) := result if {
	matched := [rule | some rule in rules; rule_matches(rule)]
	denies := [rule | some rule in matched; rule.effect == "deny"]
	count(denies) > 0
	result := {
		"decision": "deny",
		"reasons": [object.get(rule, "message", "denied by policy") | some rule in denies],
		"matched_rule_ids": [rule.id | some rule in denies],
		"approval": null,
	}
}

combine(rules, settings) := result if {
	matched := [rule | some rule in rules; rule_matches(rule)]
	count([rule | some rule in matched; rule.effect == "deny"]) == 0
	approvals := [rule | some rule in matched; rule.effect == "require_approval"]
	count(approvals) > 0
	result := {
		"decision": "require_approval",
		"reasons": [object.get(rule, "message", "") | some rule in approvals; object.get(rule, "message", "") != ""],
		"matched_rule_ids": [rule.id | some rule in matched],
		"approval": plain_requirement(approvals[0], settings),
	}
}

combine(rules, settings) := result if {
	matched := [rule | some rule in rules; rule_matches(rule)]
	count([rule | some rule in matched; rule.effect == "deny"]) == 0
	count([rule | some rule in matched; rule.effect == "require_approval"]) == 0
	count([rule | some rule in matched; rule.effect == "allow"]) > 0
	object.get(object.get(input, "tool", {}), "risk_class", "") == "W3"
	result := {
		"decision": "require_approval",
		"reasons": ["W3 writes need a second person"],
		"matched_rule_ids": [rule.id | some rule in matched],
		"approval": forced_requirement(settings),
	}
}

combine(rules, settings) := maybe_override(
	{
		"decision": "allow",
		"reasons": [],
		"matched_rule_ids": [rule.id | some rule in matched],
		"approval": null,
	},
	settings,
) if {
	matched := [rule | some rule in rules; rule_matches(rule)]
	count([rule | some rule in matched; rule.effect == "deny"]) == 0
	count([rule | some rule in matched; rule.effect == "require_approval"]) == 0
	count([rule | some rule in matched; rule.effect == "allow"]) > 0
	object.get(object.get(input, "tool", {}), "risk_class", "") != "W3"
}

combine(rules, settings) := risk_default(settings) if {
	count([rule | some rule in rules; rule_matches(rule)]) == 0
}

rule_matches(rule) if {
	match := object.get(rule, "match", {})
	field_ok(object.get(match, "tools", []), object.get(object.get(input, "tool", {}), "qualified_name", ""), true)
	field_ok(object.get(match, "servers", []), object.get(object.get(input, "tool", {}), "server_slug", ""), false)
	classes := object.get(match, "risk_classes", object.get(match, "riskClasses", []))
	field_ok(classes, object.get(object.get(input, "tool", {}), "risk_class", ""), false)
	field_ok(object.get(match, "agents", []), object.get(object.get(input, "agent", {}), "slug", ""), false)
	field_ok(object.get(match, "triggers", []), object.get(object.get(input, "run", {}), "trigger", ""), false)
	field_ok(object.get(match, "channels", []), object.get(object.get(input, "run", {}), "channel", ""), false)
	group_ok(object.get(match, "user_groups", object.get(match, "userGroups", [])), object.get(object.get(input, "user", {}), "groups", []))
	group_ok(object.get(match, "user_teams", object.get(match, "userTeams", [])), object.get(object.get(input, "user", {}), "teams", []))
	args_ok(object.get(match, "args", []))
}

field_ok(expected, _, _) if {
	count(expected) == 0
}

field_ok(expected, actual, globbing) if {
	globbing == false
	count(expected) > 0
	some item in expected
	item == actual
}

field_ok(expected, actual, globbing) if {
	globbing == true
	count(expected) > 0
	some item in expected
	glob_ok(item, actual)
}

glob_ok(pattern, text) if {
	pattern == text
}

glob_ok(pattern, _) if {
	pattern == "*"
}

glob_ok(pattern, text) if {
	endswith(pattern, ".*")
	startswith(text, trim_suffix(pattern, "*"))
}

group_ok(expected, _) if {
	count(expected) == 0
}

group_ok(expected, actual) if {
	count(expected) > 0
	some item in expected
	item in actual
}

args_ok(expected) if {
	count(expected) == 0
}

args_ok(expected) if {
	count(expected) > 0
	every item in expected {
		arg_holds(item)
	}
}

arg_holds(item) if {
	item.op == "eq"
	some value in jsonpath.values(object.get(input, "args", {}), item.path)
	value == item.value
}

arg_holds(item) if {
	item.op == "exists"
	count(jsonpath.values(object.get(input, "args", {}), item.path)) > 0
}

risk_default(settings) := maybe_override(
	{
		"decision": "allow",
		"reasons": [],
		"matched_rule_ids": [],
		"approval": null,
	},
	settings,
) if {
	object.get(object.get(input, "tool", {}), "risk_class", "") in {"R0", "R1", "W1"}
}

risk_default(settings) := {
	"decision": "require_approval",
	"reasons": ["writes that affect others wait for approval"],
	"matched_rule_ids": [],
	"approval": requester(settings),
} if {
	object.get(object.get(input, "tool", {}), "risk_class", "") == "W2"
}

risk_default(_) := {
	"decision": "deny",
	"reasons": ["W3 is denied unless a policy asks for approval"],
	"matched_rule_ids": [],
	"approval": null,
} if {
	object.get(object.get(input, "tool", {}), "risk_class", "") == "W3"
}

requester(settings) := {
	"approvers": {"mode": "requester", "groups": [], "users": []},
	"required_approvals": 1,
	"four_eyes": false,
	"step_up": false,
	"ttl_s": object.get(object.get(settings, "approvals", {}), "default_ttl_s", 86400),
	"message": "",
}

forced_requirement(settings) := {
	"approvers": {"mode": "agent_owner", "groups": [], "users": []},
	"required_approvals": 1,
	"four_eyes": true,
	"step_up": object.get(object.get(settings, "security", {}), "require_step_up_for_w3", true),
	"ttl_s": object.get(object.get(settings, "approvals", {}), "default_ttl_s", 86400),
	"message": "",
}

plain_requirement(rule, settings) := object.union(plain_fields(rule, settings), {
	"four_eyes": true,
	"step_up": true,
}) if {
	object.get(object.get(input, "tool", {}), "risk_class", "") == "W3"
	object.get(object.get(settings, "security", {}), "require_step_up_for_w3", true) == true
}

plain_requirement(rule, settings) := object.union(plain_fields(rule, settings), {"four_eyes": true}) if {
	object.get(object.get(input, "tool", {}), "risk_class", "") == "W3"
	object.get(object.get(settings, "security", {}), "require_step_up_for_w3", true) == false
}

plain_requirement(rule, settings) := plain_fields(rule, settings) if {
	object.get(object.get(input, "tool", {}), "risk_class", "") != "W3"
}

plain_fields(rule, settings) := {
	"approvers": {
		"mode": object.get(object.get(object.get(rule, "approval", {}), "approvers", {}), "mode", "requester"),
		"groups": object.get(object.get(object.get(rule, "approval", {}), "approvers", {}), "groups", []),
		"users": object.get(object.get(object.get(rule, "approval", {}), "approvers", {}), "users", []),
	},
	"required_approvals": object.get(object.get(rule, "approval", {}), "required_approvals", 1),
	"four_eyes": object.get(object.get(rule, "approval", {}), "four_eyes", false),
	"step_up": object.get(object.get(rule, "approval", {}), "step_up", false),
	"ttl_s": object.get(object.get(rule, "approval", {}), "ttl_s", object.get(object.get(settings, "approvals", {}), "default_ttl_s", 86400)),
	"message": object.get(rule, "message", ""),
}

maybe_override(result, _) := result if {
	result.decision != "allow"
}

maybe_override(result, settings) := {
	"decision": "require_approval",
	"reasons": ["the agent asks for approval on this tool"],
	"matched_rule_ids": result.matched_rule_ids,
	"approval": requester(settings),
} if {
	result.decision == "allow"
	name := object.get(object.get(input, "tool", {}), "name", "")
	flag := object.get(object.get(object.get(object.get(input, "agent", {}), "overrides", {}), name, {}), "require_approval", "")
	flag == "always"
}

maybe_override(result, _) := result if {
	result.decision == "allow"
	name := object.get(object.get(input, "tool", {}), "name", "")
	flag := object.get(object.get(object.get(object.get(input, "agent", {}), "overrides", {}), name, {}), "require_approval", "")
	flag != "always"
}
