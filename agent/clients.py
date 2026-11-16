"""LLM clients. AnthropicClient needs `pip install anthropic` and ANTHROPIC_API_KEY. ScriptedClient is for tests only."""
import os
class AnthropicClient:
    def __init__(self, model=os.environ.get('AGENT_MODEL','claude-sonnet-5-5'), max_tokens=1024):
        import anthropic; self.c=anthropic.Anthropic(); self.model=model; self.max_tokens=max_tokens
    def complete(self, system, messages, tools):
        kw={'tools':tools} if tools else {}
        r=self.c.messages.create(model=self.model,max_tokens=self.max_tokens,system=system,messages=messages,**kw)
        content=[]
        for b in r.content:
            if b.type=='text': content.append({'type':'text','text':b.text})
            elif b.type=='tool_use': content.append({'type':'tool_use','id':b.id,'name':b.name,'input':b.input})
        return {'content':content,'usage':{'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens}}
class ScriptedClient:
    """Returns pre-written responses in order. Used to test the loop; produces NO real results."""
    def __init__(self, script): self.script=list(script); self.i=0
    def complete(self, system, messages, tools):
        r=self.script[min(self.i,len(self.script)-1)]; self.i+=1
        return {'content':r,'usage':{'input_tokens':100,'output_tokens':20}}
