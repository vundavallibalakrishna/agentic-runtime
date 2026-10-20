package ar.policy_test

import rego.v1

import data.ar.policy

test_health_is_allowed if {
	policy.decision.allow with input as {"action": "health"}
}

test_other_actions_are_denied if {
	not policy.decision.allow with input as {"action": "tool.call"}
}
