"""Resume the frozen public PLD cohort without changing its original FINAL file.

Run from the project root: python research/resume_pld_supplement.py --limit 100
Requires the bundled research/bulk/contact_utils.py and discovery/resume metadata.
This only reads public sites. It does not send inquiries or verify cash availability.
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
from pathlib import Path
import signal
import threading

from pld_supplement_v3_worker import task

stop = threading.Event()


def atomic_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as file:
        for row in rows:
            file.write(json.dumps(row) + '\n')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--out', default=None)
    parser.add_argument('--state', default='research/pld_supplement_resume.json')
    args = parser.parse_args()
    if args.limit < 1 or not 1 <= args.workers <= 24:
        parser.error('--limit must be positive; --workers must be 1 through 24')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
    output = args.out or f'research/pld_supplement_resumed_{stamp}.FINAL.jsonl'
    state = json.loads(Path(args.state).read_text())
    rows = {r['source_url']: r for r in
            (json.loads(line) for line in Path(state['metrics']['final_file']).read_text().splitlines())}
    pending = sorted(state['pending_candidates'], key=lambda r: r['listing_category'] != 4)[:args.limit]
    original = len(rows)
    exclusions = []
    finished_urls = set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    iterator = iter(pending)
    with cf.ThreadPoolExecutor(args.workers) as pool:
        futures = set()
        for _ in range(min(args.workers, len(pending))):
            futures.add(pool.submit(task, next(iterator)))
        while futures:
            completed, futures = cf.wait(futures, return_when=cf.FIRST_COMPLETED)
            for future in completed:
                row, exclusion = future.result()
                if row:
                    finished_urls.add(row['source_url'])
                    if row['company'] in ('BAYFIRST', 'CREDIT LAB'):
                        exclusions.append(dict(row, reason='bank_or_credit_restoration_service'))
                    else:
                        rows[row['source_url']] = row
                else:
                    exclusions.append(exclusion)
                    finished_urls.add(exclusion['source_url'])
                if not stop.is_set():
                    seed = next(iterator, None)
                    if seed:
                        futures.add(pool.submit(task, seed))
            atomic_jsonl(output, rows.values())
    atomic_jsonl(output.replace('.jsonl', '.exclusions.jsonl'), exclusions)
    next_state = dict(state)
    next_state['completed_profile_urls'] = sorted(set(state['completed_profile_urls']) | finished_urls)
    next_state['pending_candidates'] = [r for r in state['pending_candidates']
                                        if r['profile_url'] not in finished_urls]
    next_state['metrics'] = dict(state['metrics'], final_file=output,
                                 completed_distinct=len(next_state['completed_profile_urls']),
                                 pending_raw=len(next_state['pending_candidates']))
    state_output = output.replace('.jsonl', '.resume.json')
    temporary = state_output + '.tmp'
    Path(temporary).write_text(json.dumps(next_state))
    os.replace(temporary, state_output)
    print(json.dumps({'output': output, 'retained': len(rows),
                      'new_retained': len(rows) - original,
                      'published_pairs': sum(bool(r.get('phone') and r.get('email')) for r in rows.values()),
                      'cash_threshold_verified': 0, 'stopped': stop.is_set(),
                      'next_resume_state': state_output}))


if __name__ == '__main__':
    main()
