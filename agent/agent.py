"""Tool-calling agent loop with tool routing, error recovery, and step limits.
The LLM client is pluggable (see clients.py), so the loop is testable without an API."""
import json, time
from tools import run_sql, DocSearch, get_alerts, TOOL_SCHEMAS
SYSTEM=("You are a data analyst agent for a game sales and engagement warehouse (synthetic data). "
 "Answer questions using the tools. Use search_docs for definitions and rules, run_sql for numbers, get_alerts for alerts. "
 "Never guess a number. If a tool errors, fix the query and retry. Give a short final answer that states the number or fact.")
class Agent:
    def __init__(self, client, max_steps=6, docs=None):
        self.client=client; self.max_steps=max_steps; self.docs=docs or DocSearch()
        self.registry={'search_docs':lambda a:self.docs.search(a['query']),'run_sql':lambda a:run_sql(a['query']),'get_alerts':lambda a:get_alerts()}
    def run(self, question, use_tools=True):
        msgs=[{"role":"user","content":question}]; trace={'tool_calls':0,'tool_errors':0,'steps':0,'in_tok':0,'out_tok':0,'answer':'','status':'ok'}
        t0=time.time()
        for _ in range(self.max_steps):
            r=self.client.complete(SYSTEM,msgs,TOOL_SCHEMAS if use_tools else [])
            trace['steps']+=1; trace['in_tok']+=r['usage']['input_tokens']; trace['out_tok']+=r['usage']['output_tokens']
            msgs.append({"role":"assistant","content":r['content']})
            uses=[b for b in r['content'] if b['type']=='tool_use']
            if not uses:
                trace['answer']=''.join(b.get('text','') for b in r['content'] if b['type']=='text'); break
            results=[]
            for u in uses:
                trace['tool_calls']+=1
                try:
                    if u['name'] not in self.registry: raise KeyError(f"unknown tool {u['name']}")
                    out=json.dumps(self.registry[u['name']](u['input']),default=str); err=False
                except Exception as e:
                    out=f'ERROR: {e}'; err=True; trace['tool_errors']+=1
                results.append({"type":"tool_result","tool_use_id":u['id'],"content":out,"is_error":err})
            msgs.append({"role":"user","content":results})
        else:
            trace['status']='max_steps'
        trace['latency_s']=round(time.time()-t0,3)
        return trace
