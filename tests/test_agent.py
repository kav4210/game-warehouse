import sys,os; ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,os.path.join(ROOT,'agent')); os.chdir(ROOT)
import pytest, tools, agent as ag, clients, evaluate
def T(i,n,inp): return {'type':'tool_use','id':i,'name':n,'input':inp}
def X(t): return {'type':'text','text':t}
def test_sql_guard_blocks_writes():
    for bad in ['DROP TABLE fact_sales','select 1; select 2',"update dim_game set title='x'",'pragma table_info(fact_sales)']:
        with pytest.raises(ValueError): tools.run_sql(bad)
def test_sql_runs_select():
    assert tools.run_sql('select count(*) from dim_game')['rows'][0][0]==12
def test_doc_search_finds_alert_rule():
    assert '15' in tools.DocSearch().search('alert rule revenue drop')[0]['text']
def test_agent_calls_tool_then_answers():
    c=clients.ScriptedClient([[T('1','run_sql',{'query':'select count(*) from dim_game'})],[X('There are 12 games.')]])
    t=ag.Agent(c).run('How many games?'); assert t['tool_calls']==1 and t['status']=='ok' and '12' in t['answer']
def test_agent_recovers_from_tool_error():
    c=clients.ScriptedClient([[T('1','run_sql',{'query':'select * from nope'})],[T('2','run_sql',{'query':'select count(*) from dim_game'})],[X('12')]])
    t=ag.Agent(c).run('q'); assert t['tool_errors']==1 and t['tool_calls']==2 and t['answer']=='12'
def test_unknown_tool_is_reported_not_crashed():
    c=clients.ScriptedClient([[T('1','delete_everything',{})],[X('sorry')]])
    assert ag.Agent(c).run('q')['tool_errors']==1
def test_max_steps_stops_runaway_loop():
    c=clients.ScriptedClient([[T('1','get_alerts',{})]]); t=ag.Agent(c,max_steps=3).run('q'); assert t['status']=='max_steps' and t['steps']==3
def test_ground_truth_checker():
    assert evaluate.correct('Revenue was $12,345.67','num',12345.67) and not evaluate.correct('about 99','num',12345.67)
    assert evaluate.correct('The region is NA','str','NA')
def test_questions_have_ground_truth():
    qs=evaluate.build_questions(); assert len(qs)>=30 and all(k in ('num','str') for _,k,_ in qs)
