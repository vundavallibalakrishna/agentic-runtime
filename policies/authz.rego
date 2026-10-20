package ar.policy

import rego.v1

# Interim decision until the real policy bundle lands in M5.
default decision := {"allow": false, "reason": "deny"}

decision := {"allow": true, "reason": "health"} if {
	input.action == "health"
}
