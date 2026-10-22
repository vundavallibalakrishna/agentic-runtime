package ar.jsonpath

import rego.v1

# JSONPath subset: $.a.b, $.a[0], $.a[*]. Depth is unrolled so the module stays non-recursive.
values(document, path) := walk0(document, tokens) if {
	startswith(path, "$")
	tokens := regex.find_all_string_submatch_n(`\.([A-Za-z_][A-Za-z0-9_]*)|\[(\*|\d+)\]`, path, 6)
}

default values(_, _) := []

apply(document, token) := [object.get(document, token[1], null)] if {
	token[1] != ""
	object.get(document, token[1], null) != null
}

apply(document, token) := [document[to_number(token[2])]] if {
	token[1] == ""
	token[2] != "*"
	is_array(document)
}

apply(document, token) := document if {
	token[2] == "*"
	is_array(document)
}

default apply(_, _) := []

walk0(document, tokens) := [document] if {
	count(tokens) == 0
}

walk0(document, tokens) := collected if {
	count(tokens) > 0
	collected := [value |
		some item in apply(document, tokens[0])
		some value in walk1(item, array.slice(tokens, 1, count(tokens)))
	]
}

walk1(document, tokens) := [document] if {
	count(tokens) == 0
}

walk1(document, tokens) := collected if {
	count(tokens) > 0
	collected := [value |
		some item in apply(document, tokens[0])
		some value in walk2(item, array.slice(tokens, 1, count(tokens)))
	]
}

walk2(document, tokens) := [document] if {
	count(tokens) == 0
}

walk2(document, tokens) := collected if {
	count(tokens) > 0
	collected := [value |
		some item in apply(document, tokens[0])
		some value in walk3(item, array.slice(tokens, 1, count(tokens)))
	]
}

walk3(document, tokens) := [document] if {
	count(tokens) == 0
}

default walk0(_, _) := []

default walk1(_, _) := []

default walk2(_, _) := []

default walk3(_, _) := []
