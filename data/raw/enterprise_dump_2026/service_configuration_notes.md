# Service Configuration Notes

The following notes were copied from deployment and support tickets. They are
written as operational configuration guidance rather than structured assets.

Routing source preferences:
- Flow and process lookup should prefer the graph knowledge base.
- Rules, policy snippets, and Q&A evidence should prefer the document knowledge
  base and vector search.
- Entity synonyms and relationships should be available in graph and vector
  search for retrieval expansion.
- Runtime decisions and audit events should be stored in relational state.

Retrieval thresholds:
- Use GraphRAG when the question asks how a process, flow, or task is connected.
- Use document RAG when the question asks what a policy, rule, or requirement
  says.
- Use hybrid retrieval when the question combines "how does this process work"
  with "which rule applies".
- Ask for clarification when intent is split across execution and explanation.

Approval queue configuration:
- high_value_transfer_review routes to manager_review first, then compliance
  review when screening is inconclusive.
- refinance_exception_review routes to credit_manager_review.
- automatic_debit_exception routes to loan_servicing_review.
