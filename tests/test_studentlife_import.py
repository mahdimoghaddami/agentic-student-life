import hashlib,json,tempfile,unittest
from pathlib import Path
from coach.data.importer import import_dataset
from coach.data.features import summarize
from coach.io import read_jsonl
class StudentLifeImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'EMA/response/Sleep').mkdir(parents=True)
        definition=self.root/'EMA/EMA_definition.json';definition.write_text('[]')
        self.mapping=json.loads(Path('configs/import_mapping.studentlife.json').read_text())
        self.mapping['ema_definition_sha256']=hashlib.sha256(definition.read_bytes()).hexdigest()
        self.mapping['streams']={'sleep':self.mapping['streams']['sleep']}
        self.out=self.root/'out.jsonl'
    def tearDown(self):self.tmp.cleanup()
    def run_import(self,rows):
        (self.root/'EMA/response/Sleep/Sleep_u00.json').write_text(json.dumps(rows))
        path=self.root/'mapping.json';path.write_text(json.dumps(self.mapping))
        return import_dataset(self.root,path,self.out)
    def test_categories_exclusions_and_metadata(self):
        result=self.run_import([{'null':'8','resp_time':100},{'resp_time':101},{'hour':'8','rate':'1','social':'2','resp_time':102},{'hour':'1','resp_time':103}])
        rows=read_jsonl(self.out)
        self.assertEqual(result['skipped'],2);self.assertEqual(rows[0]['value'],6.5)
        self.assertEqual(rows[0]['attributes']['daytime_sleepiness']['value'],'Once')
        self.assertEqual(rows[1]['value'],'<3 hours')
        summary=summarize(rows,'u00',104)['sleep']
        self.assertEqual(summary['prior_median_hours'],6.5)
        self.assertIsNone(summary['difference_from_prior_median'])
    def test_unknown_code_is_fatal(self):
        with self.assertRaises(ValueError):self.run_import([{'hour':'99','resp_time':100}])
        self.assertFalse(self.out.exists())
        self.assertEqual(json.loads(Path(str(self.out)+'.audit.json').read_text())['status'],'failed')
    def test_unknown_quality_is_fatal(self):
        with self.assertRaises(ValueError):self.run_import([{'hour':'8','rate':'99','resp_time':100}])
        self.assertFalse(self.out.exists())
    def test_compact_summary_uses_full_window(self):
        self.run_import([{'hour':str(i),'resp_time':100+i} for i in range(2,12)])
        s=summarize(read_jsonl(self.out),'u00',120)['sleep']
        self.assertEqual(s['count'],10);self.assertEqual(len(s['observations']),4)
        self.assertTrue(s['observations_truncated']);self.assertEqual(s['prior_median_hours'],5.5)
    def test_full_codebook(self):
        self.run_import([{'hour':str(i),'resp_time':100+i} for i in range(1,20)])
        self.assertEqual([r['value'] for r in read_jsonl(self.out)],['<3 hours',3.5,4,4.5,5,5.5,6,6.5,7,7.5,8,8.5,9,9.5,10,10.5,11,11.5,12])
