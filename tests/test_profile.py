import copy
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import workshop_profile as w
from PIL import Image, ImageChops

CONFIG=yaml.safe_load((w.ROOT/'profile.config.yml').read_text())
NOW=datetime(2026,10,1,21,0,tzinfo=ZoneInfo('Asia/Seoul'))

def item(sha='a',message='fix: handle failure'):
    return {'sha':sha,'html_url':'https://github.com/juhwan7/test/commit/'+sha,
            'commit':{'message':message,'committer':{'date':'2026-10-01T01:00:00Z'}}}

class ProfileTests(unittest.TestCase):
    def test_same_day_is_stable(self):
        self.assertEqual(w.daily_focus(CONFIG,NOW),w.daily_focus(CONFIG,NOW+timedelta(hours=2)))
    def test_next_day_changes(self):
        self.assertNotEqual(w.daily_focus(CONFIG,NOW),w.daily_focus(CONFIG,NOW+timedelta(days=1)))
    def test_repeat_generation_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertTrue(w.generate(root,CONFIG,{},NOW))
            before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertFalse(w.generate(root,CONFIG,{},NOW+timedelta(hours=1)))
            self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
    def test_manual_content_survives(self):
        text='manual introduction\n'+w.START+'old'+w.END+'\nmanual footer'
        self.assertEqual(w.replace_generated(text,w.START+'new'+w.END),'manual introduction\n'+w.START+'new'+w.END+'\nmanual footer')
    def test_partial_failure_keeps_cache_and_continues(self):
        config=copy.deepcopy(CONFIG);config['projects']=config['projects'][:2]
        repo=config['projects'][0]['repo'];old={repo:{'commits':[w.commit_record(item())],'captured_at':NOW.isoformat()}}
        def request(url,token):
            if repo in url: raise urllib.error.URLError('temporary')
            if '/commits?' in url:return [item()]
            if '/commits/' in url:return {'files':[{'filename':'src/main.py'}]}
            return {'private':False,'visibility':'public','default_branch':'main'}
        result=w.collect(config,old,NOW,request)
        self.assertEqual(result[repo]['commits'],old[repo]['commits'])
        self.assertIsNone(result[config['projects'][1]['repo']]['error'])
    def test_private_repository_drops_cached_content(self):
        repo=CONFIG['projects'][0]['repo']
        result=w.collect(CONFIG,{repo:{'commits':[w.commit_record(item())]}},NOW,
                         lambda u,t:{'private':True,'visibility':'private'})
        self.assertTrue(result[repo]['excluded'])
        self.assertNotIn('commits',result[repo])
        with self.assertRaises(ValueError): w.render_readme(CONFIG,result,NOW)
    def test_404_does_not_republish_cached_content(self):
        def fail(u,t):raise urllib.error.HTTPError(u,404,'missing',{},None)
        repo=CONFIG['projects'][0]['repo']
        result=w.collect(CONFIG,{repo:{'commits':[w.commit_record(item())]}},NOW,fail)
        self.assertTrue(result[repo]['excluded'])
        self.assertNotIn('commits',result[repo])
    def test_repeated_failure_does_not_change_timestamp(self):
        def fail(u,t):raise urllib.error.URLError('temporary')
        first=w.collect(CONFIG,{},NOW,fail)
        self.assertEqual(first,w.collect(CONFIG,first,NOW+timedelta(hours=1),fail))
    def test_routine_commits_filtered_without_filtering_bot_fixes(self):
        self.assertTrue(w.is_routine('observe: record 10-minute supervisor checkpoint'))
        self.assertTrue(w.is_routine('product: refresh market intelligence'))
        self.assertFalse(w.is_routine('fix: recover missing sensor observation'))
    def test_request_budget_and_old_change_retention(self):
        config=copy.deepcopy(CONFIG);config['projects']=config['projects'][:1]
        repo=config['projects'][0]['repo'];calls=[]
        previous={repo:{'commits':[dict(w.commit_record(item('old')),paths=['src/main.py'])]}}
        def request(u,t):
            calls.append(u)
            if '/commits?' in u: return [item(str(i),'ai-d: record event') for i in range(100)]
            if '/commits/' in u:return {'files':[{'filename':'data/event.json'}]}
            return {'private':False,'visibility':'public','default_branch':'main'}
        result=w.collect(config,previous,NOW,request)
        self.assertEqual(len(calls),6)
        self.assertEqual(result[repo]['commits'][0]['sha'],'old')
    def test_unchanged_collection_keeps_captured_at(self):
        config=copy.deepcopy(CONFIG);config['projects']=config['projects'][:1]
        def request(u,t):
            if '/commits?' in u:return [item()]
            if '/commits/' in u:return {'files':[{'filename':'src/main.py'}]}
            return {'private':False,'visibility':'public','default_branch':'main'}
        first=w.collect(config,{},NOW,request)
        self.assertEqual(first,w.collect(config,first,NOW+timedelta(hours=1),request))
    def test_markdown_escaping(self):
        result=w.markdown('a [bad](https://evil.example) | test')
        self.assertIn('\\[bad\\]',result)
        self.assertIn('\\|',result)
    def test_readme_asset_paths_exist(self):
        import re
        readme=w.render_readme(CONFIG,{},NOW)
        for path in set(re.findall(r'assets/[\w.-]+\.(?:png|gif|svg)',readme)):
            self.assertTrue((w.ROOT/path).is_file(),path)
    def test_asset_animation_and_budget(self):
        for theme in ['light','dark']:
            path=w.ROOT/f'assets/workshop-{theme}.gif'
            with Image.open(path) as gif:
                self.assertEqual(gif.n_frames,80)
                self.assertEqual(gif.info['loop'],0)
                duration=sum((gif.seek(i) or gif.info['duration']) for i in range(gif.n_frames))
                self.assertEqual(duration,8000)
                gif.seek(0);first=gif.convert('RGB');gif.seek(20)
                self.assertIsNotNone(ImageChops.difference(first,gif.convert('RGB')).getbbox())
            self.assertLess(path.stat().st_size,2_000_000)

if __name__=='__main__':unittest.main()
