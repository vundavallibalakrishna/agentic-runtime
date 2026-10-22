package ar.jsonpath_test

import rego.v1

import data.ar.jsonpath

test_field if {
	jsonpath.values({"body": {"name": "Fido"}}, "$.body.name") == ["Fido"]
}

test_index if {
	jsonpath.values({"items": ["a", "b"]}, "$.items[0]") == ["a"]
}

test_star if {
	jsonpath.values({"items": [{"ok": true}, {"ok": false}]}, "$.items[*].ok") == [true, false]
}

test_missing if {
	jsonpath.values({}, "$.missing") == []
}

test_root if {
	jsonpath.values({"ok": true}, "$") == [{"ok": true}]
}

test_missing_index if {
	jsonpath.values({"items": ["a"]}, "$.items[3]") == []
}
