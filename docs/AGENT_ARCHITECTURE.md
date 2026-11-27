# Agent execution

The LangGraph pipeline gathers catalogue state and regulation snippets, then runs orbital, collision heuristic, compliance, sustainability, forecast, mitigation and report nodes. Specialist endpoints stop after their requested node. The frontend shows returned timeline steps after execution. There is no durable worker, persisted step log or cost budget yet.

Numeric orbit and heuristic risk calculations come from backend functions. The forecast is an illustrative constant-growth scenario. It withholds collision probability in the absence of uncertainty. Regulatory snippets are local lexical retrieval results. Groq interpretation requires a configured key. Operator approval must follow evidence review and an authenticated workflow before use with customer missions.
