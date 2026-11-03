"""Explicit configurable adapter; never guesses questionnaire code meanings."""
import csv,json,hashlib
from pathlib import Path
from ..io import read_json,write_json,write_jsonl,iso,epoch

def inspect_dataset(root):
    root=Path(root); result={'root':str(root),'definition':None,'samples':{}}
    definition=root/'EMA/EMA_definition.json'
    if definition.exists(): result['definition']=read_json(definition)
    for stream,folder in [('sleep','EMA/response/Sleep'),('stress','EMA/response/Stress'),('activity','sensing/activity'),('conversation','sensing/conversation')]:
        files=sorted((root/folder).glob('*'))
        if files:
            p=files[0]
            if p.suffix=='.csv':
                with p.open(encoding='utf-8-sig',newline='') as f: data=list(csv.DictReader(f))[:3]
            else:
                data=read_json(p); data=data[:3] if isinstance(data,list) else data
            result['samples'][stream]={'file':str(p),'sample':data}
    return result

def import_dataset(root,mapping_path,output):
    root=Path(root); mapping=read_json(mapping_path)
    definition=root/'EMA/EMA_definition.json'
    if not definition.exists(): raise ValueError('Missing EMA/EMA_definition.json')
    actual=hashlib.sha256(definition.read_bytes()).hexdigest()
    if mapping.get('ema_definition_sha256')!=actual:
        raise ValueError('Mapping must contain SHA256 of your reviewed EMA_definition.json; run inspect first')
    records=[]; errors=[]; skipped=[]; seen=set(); duplicates=0
    for stream,spec in mapping['streams'].items():
        files=sorted(root.glob(spec['glob']))
        if not files: errors.append({'stream':stream,'error':'No matching files'})
        for p in files:
            participant=p.stem.split('_')[-1]
            if p.suffix=='.csv':
                with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
            else:
                rows=read_json(p)
                if spec.get('records_key'): rows=rows[spec['records_key']]
            if not isinstance(rows,list): raise ValueError(f'{p}: configure records_key for this JSON structure')
            for index,raw in enumerate(rows):
                try:
                    row={k.strip():v for k,v in raw.items()}
                    field=spec.get('value_field')
                    if field and (field not in row or row[field] is None or row[field]=='') and spec.get('skip_missing_answer',False):
                        skipped.append({'file':str(p.relative_to(root)),'row':index,'stream':stream,'reason':'missing_named_answer','field':field})
                        continue
                    observed=iso(row[spec['observed_field']]); available=iso(row[spec['available_field']])
                    if stream=='conversation': value=None
                    else:
                        code=str(row[spec['value_field']])
                        if code in [str(x) for x in spec.get('missing_codes',[])]:
                            skipped.append({'file':str(p.relative_to(root)),'row':index,'stream':stream,'reason':'documented_missing_code','field':spec['value_field']})
                            continue
                        if 'values' in spec:
                            if code not in spec['values']: raise ValueError(f'Unknown {stream} code {code}')
                            value=spec['values'][code]
                        else: value=row[spec['value_field']]
                    rec={'participant_id':participant,'stream':stream,'observed_at':observed,'available_at':available,'value':value,'source':'studentlife','source_file':str(p.relative_to(root))}
                    if field:
                        rec['raw_code']=code
                    for name,extra in spec.get('extra_fields',{}).items():
                        extra_code=row.get(extra['field'])
                        if extra_code is None or extra_code=='': continue
                        extra_code=str(extra_code)
                        if extra_code not in extra['values']: raise ValueError(f'Unknown {stream}.{name} code {extra_code}')
                        rec.setdefault('attributes',{})[name]={'raw_code':extra_code,'value':extra['values'][extra_code]}
                    if stream=='conversation':
                        rec['end_at']=iso(row[spec['end_field']])
                        if epoch(rec['end_at'])<epoch(observed): raise ValueError('Negative interval')
                        # A completed interval cannot be available before its end.
                        rec['available_at']=iso(max(epoch(available),epoch(rec['end_at'])))
                    signature=json.dumps(rec,sort_keys=True)
                    if signature in seen:
                        duplicates+=1
                        continue
                    seen.add(signature); rec['id']=hashlib.sha256(signature.encode()).hexdigest()[:20]; records.append(rec)
                except (KeyError,ValueError,TypeError) as exc: errors.append({'file':str(p),'row':index,'error':str(exc)})
    report={'status':'failed' if errors else 'ok','records':len(records),'skipped_count':len(skipped),'skipped':skipped,'duplicates_removed':duplicates,'error_count':len(errors),'definition_sha256':actual}
    write_json(str(output)+'.audit.json',report)
    if errors:
        write_json(str(output)+'.errors.json',errors)
        raise ValueError(f'{len(errors)} import errors; see {output}.errors.json. No partial dataset written.')
    from .features import validate_records
    validate_records(records); write_jsonl(output,records)
    return {'skipped':len(skipped),'audit':str(output)+'.audit.json','records':len(records),'participants':len(set(r['participant_id'] for r in records)),'definition_sha256':actual}
