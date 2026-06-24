# NISB Room MCP External Publish User and Integration Guide

Version: P1 Initial Release  
Audience: NISB room owners, external MCP client users, system integrators  
Scope: room-scoped external MCP publish

## 1. Overview

NISB Room MCP External Publish lets a room owner publish one NISB room as a standard MCP-accessible service.

After an external application connects, it can ask only that published room and receive the room’s final answer.

The external application does not need to know how many workers the room has, whether it uses RAG, whether it calls builtin MCP tools, or whether a supervisor coordinates the answer.

It sends a question to the NISB MCP endpoint and receives a final text response.

MCP is a protocol for connecting AI applications to external tools and data sources, and MCP servers can expose tools that clients discover and invoke. 
In NISB, a published room is wrapped as a room provider that an external MCP client can call.

## 2. Use Cases

NISB Room MCP External Publish is useful when you want to connect a configured NISB room to another AI application.

Typical use cases:

```text
Connect a knowledge-base room to an external chat tool.
Connect a RAG-powered expert Q&A room to an internal team AI platform.
Expose a supervisor + workers workflow as one external question-answer capability.
Connect a room that uses builtin MCP tools to a third-party MCP client.
Safely publish one owner-managed room to a selected external system.
```

The external application sees a simplified MCP interface, not the full NISB room list.

## 3. Core Boundary

NISB Room MCP External Publish is room-scoped.

This means:

```text
One external_mcp_publish_token maps to one published room.
The external client cannot browse all NISB rooms.
The external client cannot directly access rooms owned by other users.
The external client cannot access worker execution traces.
The external client cannot see source observations.
The external client receives only final-only answers.
```

This is not federation grant externalization.

Do not give `room-mcp-grant:<payload>` to third-party clients.

Third-party clients use `external_mcp_publish_token`.

## 4. Before Publishing

Before enabling Room MCP External Publish, configure and test the source room inside NISB.

Recommended preparation:

```text
1. Open the NISB room you want to publish.
2. Open room settings.
3. Configure the supervisor.
4. Configure each worker.
5. Attach RAG / knowledge sources if needed.
6. Attach builtin MCP tools if needed.
7. Configure room MCP / nested room MCP if needed.
8. Ask normal questions inside the room first.
9. Confirm the room returns the expected final answer.
```

External MCP publish does not redesign your room.

It safely exposes the room’s existing question-answer and orchestration capability through an MCP endpoint.

## 5. Enable External Publish

Open the target room and go to:

```text
Room Settings -> Room MCP External Publish
```

Click:

```text
Enable External Publish
```

After success, NISB generates:

```text
MCP endpoint
external_mcp_publish_token
provider_id
source_room_id
MCP client config
```

The most important connection information is:

```text
Endpoint: https://nisb.example.com/nisb/mcp
Authorization: Bearer <external_mcp_publish_token>
```

The token is the credential that allows an external system to access the published room.

Do not publish the token publicly.

Do not commit the token to a repository.

Do not paste the token into untrusted chats, logs, tickets, or documents.

## 6. Token Options

When publishing or regenerating a token, the owner can configure:

```text
Validity period
Maximum successful question count
Client label
Endpoint
```

Validity rules:

```text
Minimum validity: 1 hour.
Maximum validity: 30 days.
Default validity: 30 days.
0.0417 days is approximately 1 hour.
Expired tokens stop working.
```

Call limit rules:

```text
Empty max_calls means unlimited.
max_calls=0 means unlimited.
max_calls=1 allows one successful room question.
max_calls=N allows N successful room questions.
initialize, tools/list, and room_provider_list do not consume max_calls.
Only successful room_provider_call consumes max_calls.
```

Examples:

```text
Validity: 0.0417 days, max_calls: 1
Result: one successful question, then the token is over limit.

Validity: 30 days, max_calls empty
Result: valid for about 30 days with no successful-question count limit.

Validity: 50 days
Result: rejected because the maximum is 30 days.
```

## 7. Copy Client Config

After publishing, copy the MCP client config from the UI.

Recommended generic config:

```json
{
  "type": "streamable-http",
  "url": "https://nisb.example.com/nisb/mcp",
  "headers": {
    "Authorization": "Bearer <external_mcp_publish_token>"
  }
}
```

If your external client supports environment variables, store the token in an environment variable instead of hardcoding it in the config.

Example:

```text
NISB_ROOM_MCP_TOKEN=<external_mcp_publish_token>
```

Then reference the environment variable in the external client config.

## 8. External Tools

After a successful connection, the external MCP client should see two tools:

```text
room_provider_list
room_provider_call
```

Tool usage:

| Tool | Purpose |
|---|---|
| `room_provider_list` | List the room provider authorized by the current token |
| `room_provider_call` | Ask the authorized room a question |

`room_provider_list` should return exactly one provider.

Expected provider list shape:

```text
count=1
provider_id=room_provider__<source_room_id>
source_room_id=<source_room_id>
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

The core input for `room_provider_call` is:

```text
question
```

Example:

```json
{
  "question": "What can this room help with?"
}
```

## 9. Client Requirements

An external system should support:

```text
MCP
Streamable HTTP transport
Configurable URL
Configurable Authorization Bearer header
initialize
tools/list
tools/call
text content results
```

The MCP Streamable HTTP transport uses a server-provided MCP endpoint over HTTP, while stdio is a separate standard transport option. [modelcontextprotocol](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

If a platform supports only stdio, only OAuth, cannot configure headers, or rewrites tool names in an incompatible way, it may need additional adaptation.

## 10. Generic Integration Flow

Use this process for most external MCP clients:

```text
1. Enable Room MCP External Publish in the NISB room.
2. Copy the MCP endpoint and Bearer token.
3. Add a new MCP server in the external MCP client.
4. Select streamable-http transport.
5. Set URL to https://nisb.example.com/nisb/mcp.
6. Add header Authorization: Bearer <external_mcp_publish_token>.
7. Save and restart or refresh the external client if needed.
8. Confirm initialize succeeds.
9. Confirm tools/list shows room_provider_list and room_provider_call.
10. Call room_provider_list and confirm count=1.
11. Call room_provider_call and confirm the room returns a final answer.
```

If your client has a UI for adding MCP servers, fill in the transport, URL, and Authorization header in that UI.

## 11. LibreChat Integration Example

LibreChat can be configured with an MCP server entry in `librechat.yaml`.

Example:

```yaml
mcpServers:
  nisb:
    type: streamable-http
    url: https://nisb.example.com/nisb/mcp
    headers:
      Authorization: Bearer ${NISB_ROOM_MCP_TOKEN}
    chatMenu: true
    startup: true
    serverInstructions: false
    initTimeout: 60000
    timeout: 300000
```

LibreChat supports MCP server configuration and supports environment variable references in headers for SSE and Streamable HTTP transports. 

Recommended server key:

```text
nisb
```

Avoid names containing:

```text
_mcp_
```

Some clients append or rewrite tool names.

Short server keys and short tool names reduce compatibility risk.

## 12. LibreChat Usage

After integration, ask the model to use the NISB MCP tools.

Test prompt:

```text
You must use the enabled NISB Room MCP tools. Do not answer directly.
Call room_provider_list and tell me the count and provider_id.
```

Expected result:

```text
count=1
provider_id=room_provider__<source_room_id>
```

Then test a room question:

```text
You must use the enabled NISB Room MCP tools. Do not answer directly:
What can this room help with?
```

Expected behavior:

```text
LibreChat calls room_provider_call.
NISB source room runs its supervisor / workers according to its own settings.
The external page shows only the final answer.
```

Observed successful LibreChat log shape:

```text
[MCP][nisb] URL: https://nisb.example.com/nisb/mcp
[MCP][nisb] OAuth Required: false
[MCP][nisb] Capabilities: {"tools":{}}
[MCP][nisb] Tools: room_provider_list, room_provider_call
[MCP][nisb] Initialized in: <ms>
```

## 13. MCP Inspector Integration

Use a connection mode that supports remote Streamable HTTP.

Connection values:

```text
URL: https://nisb.example.com/nisb/mcp
Header: Authorization
Value: Bearer <external_mcp_publish_token>
```

Validation order:

```text
1. initialize succeeds.
2. tools/list succeeds.
3. room_provider_list appears.
4. room_provider_call appears.
5. Call room_provider_list.
6. Confirm count=1.
7. Call room_provider_call.
8. Confirm real room text is returned.
```

If initialize succeeds but tools/call fails, check:

```text
Token value
Authorization header format
Endpoint
Tool name
Client cache
Whether the token was revoked, expired, regenerated, or over limit
```

## 14. Claude Desktop and stdio-only Clients

Some MCP clients may support stdio but not direct Streamable HTTP server configuration.

If a client supports only stdio, it may need a local bridge that forwards stdio requests to the NISB Streamable HTTP endpoint.

Compatibility guide:

```text
Streamable HTTP + Bearer header: direct connection should be possible.
stdio-only: bridge may be required.
OAuth-only: not guaranteed in P1.
No configurable Authorization header: not guaranteed in P1.
```

## 15. Token Management

The external MCP publish token is the credential for the published room.

Rules:

```text
Do not publish the token.
Do not put the token in public documentation.
Do not commit the token to a code repository.
Do not send the token to untrusted third parties.
Regenerate the token immediately if it leaks.
```

The room owner can:

```text
Regenerate token.
Revoke external access.
Set validity period.
Set maximum successful question count.
View used_count.
View last_used_at.
```

Expected behavior:

```text
After regenerate, the old token fails.
After revoke, the token fails.
After expiry, the token fails.
After max_calls is exceeded, provider_call fails.
```

## 16. Security Model

NISB Room MCP External Publish uses a strict single-room security model:

```text
One token maps to one room.
One token maps to one provider_id.
provider_list returns one provider.
provider_call can call only that provider.
Results are final-only.
source_observation is not returned.
owner private scope is not exposed.
worker traces are not exposed.
```

The external client cannot use this token to enumerate other NISB rooms.

The external client cannot bypass the source room’s supervisor, workers, reply mode, or room policies.

## 17. Source Room Capabilities

External publish does not weaken source room capabilities.

If the source room uses:

```text
supervisor
workers
RAG
knowledge base
builtin MCP
nested room MCP
workspace / skill / fs / notebook policy
```

then external calls should still run through the source room’s own configuration.

The external client only sends a question.

It does not need to understand the source room’s internal orchestration.

Validated examples:

```text
direct_role reply mode works through external MCP calls.
supervisor direct-answer mode works through external MCP calls.
notebook_write_enabled side-memory scenario works through external MCP calls.
```

## 18. Results

The external client should receive a text answer.

P1 target:

```text
final-only answer
```

Not guaranteed in P1:

```text
worker trace display
source observation display
image rendering in every client
rich media rendering in every client
full private execution trace export
```

If a client does not display images, cards, or rich media, that is usually a client rendering limitation.

It does not invalidate the core NISB Room MCP External Publish behavior.

## 19. Common Questions

### Q1: Does the external system need to know the room’s workers?

No.

The external system calls `room_provider_call`.

NISB runs the source room’s supervisor and workers internally.

### Q2: Can the external system see other rooms?

No.

room-scoped external MCP publish means one token can access only one published room.

### Q3: Can I give a federation room-mcp-grant to a third-party client?

No.

Third-party clients should use `external_mcp_publish_token`, not `room-mcp-grant:<payload>`.

### Q4: Why are the external tool names room_provider_list and room_provider_call?

The names are short and stable for client compatibility.

NISB maps them internally to canonical tools.

### Q5: Why does the external client see only two tools?

P1 uses a static external tool design.

The external client does not need a dynamic per-room tool catalog.

It only needs to list the authorized provider and ask that provider a question.

### Q6: What if LibreChat does not show images?

That does not block P1 validation.

P1 targets final-only text answers.

### Q7: What if the owner room shows the external caller as unknown?

This is a display polish issue, not a P1 access failure.

Future versions may show the sender as External MCP Client or use the configured client label.

### Q8: What if the second question fails?

Check whether max_calls was set to 1.

If max_calls=1, the first successful room question consumes the token’s allowed call count.

### Q9: What if the token stops working after about one hour?

Check whether validity was set to 0.0417 days.

That value is approximately one hour.

### Q10: What if I set 50 days and receive an error?

That is expected.

P1 limits token validity to a maximum of 30 days.

## 20. Recommended Validation Checklist

After publishing a room, validate:

```text
Normal room question works inside NISB.
Room supervisor is configured.
Workers are configured.
RAG / builtin MCP works if needed.
Room MCP External Publish is enabled.
Copied config includes endpoint and Bearer token.
External client initialize succeeds.
External client tools/list succeeds.
room_provider_list returns count=1.
room_provider_call returns real room text.
External client cannot see other rooms.
Revoke makes the old token fail.
Regenerate makes the old token fail and the new token work.
Expiry makes the token fail.
max_calls behaves as configured.
used_count and last_used_at update after successful calls.
```

Minimum access validation:

```text
tools/list succeeds.
room_provider_list returns count=1.
room_provider_call returns real room text.
```

Token lifecycle validation:

```text
max_calls=1 succeeds once and fails second call.
max_calls empty allows repeated calls.
0.0417-day token expires after about one hour.
50-day validity is rejected.
regenerate invalidates the old token.
revoke invalidates the token.
```

## 21. Verified Clients

Currently verified:

```text
minimal Node MCP client
MCP Inspector local application
LibreChat
```

Validated behavior:

```text
initialize
tools/list
room_provider_list
room_provider_call
Bearer token
single-room scope
final-only text response
token revoke
token regenerate
token expiry
max_calls
used_count / last_used_at
```

Future validation:

```text
Claude Desktop
stdio bridge scenarios
more third-party MCP platforms
```

Based on the current validation, an external client should be a good candidate if it supports:

```text
MCP Streamable HTTP
Authorization Bearer header
tools/list
tools/call
text result display
```

## 22. External Config Summary

Shortest integration summary:

```text
Transport: streamable-http
URL: https://nisb.example.com/nisb/mcp
Header: Authorization: Bearer <external_mcp_publish_token>
Tools:
  room_provider_list
  room_provider_call
```

Minimal call model:

```text
Run tools/list.
Call room_provider_list.
Call room_provider_call with question.
```

Minimal security boundary:

```text
One token.
One room.
One provider.
Final-only answer.
```

## 23. Recommended Handoff to External System Teams

If you are giving one NISB room to an external system, prepare it this way:

```text
First configure and test the room inside NISB.
Enable Room MCP External Publish.
Copy the MCP client config.
Give the external system only the endpoint and token.
Do not give NISB internal grants.
Do not give other room information.
Do not expose worker private details.
```

If the external system asks “How do we connect?”, provide:

```text
URL: https://nisb.example.com/nisb/mcp
Transport: streamable-http
Authorization: Bearer <external_mcp_publish_token>
```

If the external system asks “How do we call it?”, provide:

```text
Call room_provider_list to inspect the authorized provider.
Call room_provider_call with a question.
```

## 24. Current Release Conclusion

NISB Room MCP External Publish has the core capability needed for external system integration.

It has completed:

```text
room owner publish
Bearer token access
single-room scope
standard MCP tools/list
standard MCP tools/call
external client invocation
minimal Node client validation
MCP Inspector local application validation
LibreChat real third-party integration
token revoke
token regenerate
token expiry
max_calls
used_count / last_used_at
final-only text answer
federation/imported_remote minimum regression
```

P1 release statement:

```text
NISB supports room-scoped external MCP publish.

A room owner can generate a revocable, expiring, call-limited external MCP token/config for one room.
External MCP clients that support Streamable HTTP and Authorization Bearer headers can connect to that room.
They can discover the NISB room provider with room_provider_list and ask it questions with room_provider_call.
The external client receives final-only answers governed by the source room’s configuration.
```

Post-P1 enhancement areas:

```text
Claude Desktop validation.
stdio bridge documentation.
More client-specific examples.
External sender display polish.
Schema minimization.
More complete runtime worker regression matrix.
More compatibility notes for client-specific behavior.
```

