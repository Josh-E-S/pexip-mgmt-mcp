# Dial plan — gateway routing rules

For configuring how unmatched incoming calls are bridged to external destinations (Teams, SIP, H.323, MS-SIP, RTMP). Pexip's gateway routing rules are like Asterisk extensions or an Avaya dial plan: a regex matches the dialed string, an optional replacement rewrites it, and the call is bridged onward on a specified protocol.

## Mental model

When a call arrives:

1. Pexip looks for a `conference_alias` that **exactly** matches the dialed string → routes to that VMR.
2. If no alias matches, Pexip evaluates **gateway routing rules** in ascending `priority` order.
3. **First rule whose `match_string` regex matches wins.** The call is bridged onward using that rule's `outgoing_protocol` and `outgoing_location`.
4. No rule matches → call is rejected.

Lower priority = evaluated earlier. Plan priority numbers with gaps (10, 20, 30) so you can insert rules in between later.

## Recipe: list rules in evaluation order

```
list_gateway_rules(enabled_only=True)   # ordered by priority ascending
```

## Recipe: add a rule (bridge SIP → Teams)

```
create_gateway_rule(
    name="route-teams-meetings",
    priority=100,
    match_string="^teams\\.([0-9]+)@example\\.com$",
    replace_string="\\1@m.webex.com",          # or a Teams CVI alias
    called_device_type="external",
    outgoing_protocol="sip",
    outgoing_location="eu-west",               # name or id
    call_type="video",
    crypto_mode="best_effort",
    enable=True,
    description="Inbound teams.<id> → Teams meeting",
)
```

`called_device_type` values: `mssip` / `lync` / `external` / `registration` / `gms`.
`outgoing_protocol` values: `sip` / `h323` / `mssip` / `rtmp` / `teams`.
`crypto_mode` values: `best_effort` / `required` / `none`.

## Recipe: re-prioritize a rule

```
update_gateway_rule(rule="route-teams-meetings", priority=50)
```

Other rules' priorities are **not** auto-shifted. If another rule already has priority 50 you'll have two rules at the same priority — order between them becomes unstable. Renumber both, or pick a gap (e.g. priority=45).

## Recipe: disable instead of delete

```
update_gateway_rule(rule="route-teams-meetings", enable=False)
```

Disabled rules stay in the config (and in `list_gateway_rules()` unless filtered) but are skipped during evaluation. Reversible. Prefer this for rules you might want back.

## Recipe: delete a rule

```
delete_gateway_rule(rule="route-teams-meetings")
```

Irreversible. Confirm with the user first.

## Regex tips

- Pexip uses standard regex syntax (PCRE-flavored). Anchor with `^…$` to avoid partial matches.
- Backreferences in `replace_string` use `\1`, `\2`, etc. — escape backslashes for JSON.
- Test patterns against representative dial strings BEFORE rolling out — a too-broad regex can swallow calls that should hit a different rule.
- `match_string` is matched against the dial string **as received**, including any leading `+` or protocol prefix.

## Field gotchas

- **`outgoing_location` is a FK.** Pass the location name or id; the MCP tool resolves to a URI internally.
- **Booleans in filters** sometimes need to be Python-cased (`enabled_only=True` → query `enable=True`). The MCP tool handles this for `list_gateway_rules`.
- **`crypto_mode="required"` will hard-fail calls** to destinations that don't support encryption — common gotcha for legacy H.323 endpoints.

## Authoritative docs

- Gateway services overview: https://docs.pexip.com/admin/configuring_gateway.htm
- Calling MS Teams via CVI: https://docs.pexip.com/admin/configuring_msteams_cvi.htm
- Configuration API rule schema: https://docs.pexip.com/api_manage/api_configuration.htm (search `gateway_routing_rule`)
