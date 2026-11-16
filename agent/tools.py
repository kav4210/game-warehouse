"""Tools the agent can call. All read-only."""
import json, re, sqlite3, os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB=os.path.join(ROOT,'data','warehouse.db')
_BANNED=re.compile(r'\b(insert|update|delete|drop|alter|create|attach|pragma|replace)\b',re.I)

def run_sql(query, db=DB):
    q=query.strip().rstrip(';')
    if not q.lower().startswith(('select','with')) or _BANNED.search(q) or ';' in q:
        raise ValueError('Only a single read-only SELECT query is allowed')
    con=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
    try:
        cur=con.execute(q); cols=[c[0] for c in cur.description]
        rows=cur.fetchmany(50)
    finally: con.close()
    return {'columns':cols,'rows':rows,'truncated':len(rows)==50}

class DocSearch:
    def __init__(self, paths=None):
        paths=paths or [os.path.join(ROOT,'docs','data_dictionary.md'),os.path.join(ROOT,'README.md')]
        self.chunks=[]
        for p in paths:
            for para in re.split(r'\n\s*\n|\n(?=#)',open(p).read()):
                if len(para.strip())>20: self.chunks.append(para.strip())
        self.vec=TfidfVectorizer(stop_words='english'); self.m=self.vec.fit_transform(self.chunks)
    def search(self, query, k=3):
        s=cosine_similarity(self.vec.transform([query]),self.m)[0]
        idx=s.argsort()[::-1][:k]
        return [{'score':round(float(s[i]),3),'text':self.chunks[i]} for i in idx if s[i]>0]

def get_alerts(path=os.path.join(ROOT,'data','alerts.json')):
    return json.load(open(path))

TOOL_SCHEMAS=[
 {"name":"search_docs","description":"Search the warehouse documentation (data dictionary, README) for definitions, table grains, and business rules.","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
 {"name":"run_sql","description":"Run ONE read-only SQLite SELECT against the warehouse. Tables: fact_sales, fact_engagement, dim_date, dim_game, dim_region, dim_channel, mart_game_quarterly, mart_region_channel, mart_engagement. Returns up to 50 rows.","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
 {"name":"get_alerts","description":"Return the latest data-quality results and quarter-over-quarter revenue-drop alerts.","input_schema":{"type":"object","properties":{}}},
]
