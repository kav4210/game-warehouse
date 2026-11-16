"""Run the agent vs a no-tools baseline on questions whose ground truth is computed from the warehouse.
Usage  python agent/evaluate.py            (needs ANTHROPIC_API_KEY)  -> writes agent/results.json"""
import json, re, sqlite3, statistics, sys, os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from tools import DB
def build_questions(db=DB):
    c=sqlite3.connect(db); q=[]
    games=[r[0] for r in c.execute('select title from dim_game order by game_key')]
    for g in games:
        for qt in (1,3):
            v=c.execute('select revenue from mart_game_quarterly where title=? and quarter=?',(g,qt)).fetchone()
            if v: q.append((f'What was total revenue for the game "{g}" in quarter {qt} of 2024? Give the dollar amount.','num',v[0]))
    top_region=c.execute('select region,sum(revenue) r from mart_region_channel group by region order by r desc').fetchall()
    q.append(('Which region had the highest total revenue? Name the region code.','str',top_region[0][0]))
    q.append(('Which region had the lowest total revenue? Name the region code.','str',top_region[-1][0]))
    q.append(('Which genre had the highest total revenue across 2024?','str',c.execute('select genre from mart_game_quarterly group by genre order by sum(revenue) desc limit 1').fetchone()[0]))
    q.append(('How many total units were sold through the digital channel?','num',c.execute("select sum(units) from mart_region_channel where channel='digital'").fetchone()[0]))
    q.append(('How many total units were sold through the retail channel?','num',c.execute("select sum(units) from mart_region_channel where channel='retail'").fetchone()[0]))
    q.append(('How many sales rows are in fact_sales?','num',c.execute('select count(*) from fact_sales').fetchone()[0]))
    q.append(('How many games are in dim_game?','num',c.execute('select count(*) from dim_game').fetchone()[0]))
    q.append(('Which game had the highest average active players? Give the title.','str',c.execute('select title from mart_engagement group by title order by avg(avg_active_players) desc limit 1').fetchone()[0]))
    q.append(('According to the documentation, what percentage quarter-over-quarter revenue drop triggers an alert?','num',15))
    q.append(('How many duplicate sale IDs did the data-quality gate find in the raw data?','num',json.load(open(os.path.join(os.path.dirname(DB),'alerts.json')))['quality']['duplicate_sale_ids']))
    return q
def correct(answer, kind, truth):
    if kind=='str': return str(truth).lower() in answer.lower()
    nums=[float(x.replace(',','')) for x in re.findall(r'\d[\d,]*\.?\d*',answer) if x.replace(',','').replace('.','',1).isdigit()]
    tol=0.51 if float(truth)>100 else 0.01
    return any(abs(n-float(truth))<=tol for n in nums)
def evaluate(agent, questions, use_tools=True):
    rows=[]
    for text,kind,truth in questions:
        t=agent.run(text,use_tools=use_tools); t.update(question=text,truth=truth,correct=correct(t['answer'],kind,truth)); rows.append(t)
    n=len(rows)
    return {'n':n,'success_rate':round(sum(r['correct'] for r in rows)/n,3),'avg_tool_calls':round(statistics.mean(r['tool_calls'] for r in rows),2),
            'tool_error_rate':round(sum(r['tool_errors'] for r in rows)/max(1,sum(r['tool_calls'] for r in rows)),3),
            'median_latency_s':round(statistics.median(r['latency_s'] for r in rows),2),'avg_tokens':round(statistics.mean(r['in_tok']+r['out_tok'] for r in rows)),
            'max_step_failures':sum(r['status']=='max_steps' for r in rows)}, rows
if __name__=='__main__':
    from agent import Agent; from clients import AnthropicClient
    a=Agent(AnthropicClient()); qs=build_questions()
    base,_=evaluate(a,qs,use_tools=False); res,rows=evaluate(a,qs,use_tools=True)
    json.dump({'baseline_no_tools':base,'agent':res,'rows':rows},open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results.json'),'w'),indent=2,default=str)
    print('BASELINE',base); print('AGENT',res)
