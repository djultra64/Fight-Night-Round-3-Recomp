#!/usr/bin/env python3
"""Analyze opt-in guest swap routine cadence, never GPU/presentation FPS.

Project work: djultra64. Reads local traces; never starts or benchmarks the game.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer')
    return value


def validate(metadata, samples):
    if not isinstance(metadata, dict) or not isinstance(samples, list):
        raise ValueError('metadata must be an object and samples must be a list')
    if (metadata.get('type') != 'metadata' or type(metadata.get('schema_version')) is not int
            or metadata['schema_version'] != 1):
        raise ValueError('unsupported trace metadata/schema')
    if metadata.get('clock') != 'steady_clock' or metadata.get('source') != 'guest_swap_routine_entry':
        raise ValueError('unsupported timing source; expected guest swap routine entry')
    if metadata.get('cache_state') not in ('cold', 'warm', 'unknown'):
        raise ValueError('cache_state must be cold, warm or unknown')
    fields = ['origin_ns', 'capacity', 'total_samples', 'retained_samples',
              'overwritten_samples', 'contention_drops']
    for field in fields: integer(metadata.get(field), field)
    if not metadata['capacity'] or metadata['retained_samples'] > metadata['capacity']:
        raise ValueError('invalid ring capacity/retained count')
    if metadata['retained_samples'] != len(samples):
        raise ValueError('sample count differs from metadata')
    if metadata['retained_samples'] + metadata['overwritten_samples'] != metadata['total_samples']:
        raise ValueError('total/retained/overwritten sample counts disagree')
    previous = None
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict): raise ValueError('sample must be an object')
        if sample.get('type') != 'sample': raise ValueError('unexpected trace record type')
        sequence = integer(sample.get('sequence'), 'sequence')
        timestamp = integer(sample.get('steady_ns'), 'steady_ns')
        if sequence != metadata['overwritten_samples'] + index:
            raise ValueError('sample sequences are not contiguous/in ring order')
        if timestamp < metadata['origin_ns'] or (previous is not None and timestamp <= previous):
            raise ValueError('timestamps must strictly increase and follow trace origin')
        previous = timestamp


def read_trace(path):
    with Path(path).open(encoding='utf-8') as stream:
        try:
            metadata = json.loads(next(stream))
            samples = [json.loads(line) for line in stream if line.strip()]
        except (StopIteration, json.JSONDecodeError) as error:
            raise ValueError(f'invalid JSONL trace: {error}') from error
    validate(metadata, samples)
    return metadata, samples


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def bursts(intervals, threshold_ns):
    result, current = [], []
    for interval in intervals:
        if interval['interval_ns'] > threshold_ns:
            current.append(interval)
        elif current:
            result.append(current); current = []
    if current: result.append(current)
    events = [{'first_sequence': event[0]['sequence'],
               'last_sequence': event[-1]['sequence'],
               'interval_count': len(event),
               'total_ms': sum(i['interval_ns'] for i in event) / 1e6,
               'max_ms': max(i['interval_ns'] for i in event) / 1e6,
               'start_seconds': event[0]['start_seconds'],
               'end_seconds': event[-1]['end_seconds']} for event in result]
    return {'count': len(events), 'longest_consecutive_intervals': max((len(e) for e in result), default=0),
            'largest_bursts': sorted(events, key=lambda e: (e['interval_count'], e['total_ms']), reverse=True)[:10]}


def analyze(metadata, samples, *, start_seconds=0.0, window_seconds=None,
            minimum_seconds=30.0, expect_cache=None, target_fps=30.0):
    """Report guest entry cadence; target_fps defaults to the historical 30 Hz.

    Percentiles use nearest rank. The 1% low rate is 1000 divided by the
    arithmetic mean in ms of the slowest ceil(interval_count / 100) intervals.
    Neither rate represents GPU completion, unique frames, or presentation.
    """
    validate(metadata, samples)
    if (isinstance(target_fps, bool) or not isinstance(target_fps, (int, float))
            or not math.isfinite(target_fps) or target_fps <= 0):
        raise ValueError('target_fps must be finite and positive')
    budget_ns = 1e9 / target_fps
    if not math.isfinite(budget_ns) or budget_ns <= 0:
        raise ValueError('target_fps must yield a finite positive interval budget')
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError('start_seconds must be finite and nonnegative')
    if window_seconds is not None and (not math.isfinite(window_seconds) or window_seconds <= 0):
        raise ValueError('window_seconds must be finite and positive')
    if not math.isfinite(minimum_seconds) or minimum_seconds < 0:
        raise ValueError('minimum_seconds must be finite and nonnegative')
    if expect_cache is not None and expect_cache not in ('cold', 'warm'):
        raise ValueError('expect_cache must be cold or warm')
    start_ns = start_seconds * 1e9
    window_ns = window_seconds * 1e9 if window_seconds is not None else None
    if not math.isfinite(start_ns) or (window_ns is not None and not math.isfinite(window_ns)):
        raise ValueError('requested window must fit a finite nanosecond range')
    # Trace timestamps are integer ns. Round each requested boundary component
    # once so decimal windows such as 0.1 + 0.2 do not lose their last sample.
    start_ns = round(start_ns)
    end_ns = start_ns + round(window_ns) if window_ns is not None else None
    origin = metadata['origin_ns']
    selected = [sample for sample in samples
                if sample['steady_ns'] - origin >= start_ns
                and (end_ns is None or sample['steady_ns'] - origin <= end_ns)]
    intervals = [{'sequence': right['sequence'],
                  'interval_ns': right['steady_ns'] - left['steady_ns'],
                  'start_seconds': (left['steady_ns'] - origin) / 1e9,
                  'end_seconds': (right['steady_ns'] - origin) / 1e9}
                 for left, right in zip(selected, selected[1:])]
    # Keep historical cadence statistics restricted to fully contained
    # intervals, but retain the adjacent evidence before filtering it away.
    crossing_intervals = []
    for left, right in zip(samples, samples[1:]):
        left_ns, right_ns = left['steady_ns'] - origin, right['steady_ns'] - origin
        crosses_start = left_ns < start_ns < right_ns
        crosses_end = end_ns is not None and left_ns < end_ns < right_ns
        if crosses_start or crosses_end:
            crossing_intervals.append({
                'sequence': right['sequence'], 'interval_ns': right_ns - left_ns,
                'interval_ms': (right_ns - left_ns) / 1e6,
                'start_seconds': left_ns / 1e9, 'end_seconds': right_ns / 1e9,
                'crosses_start': crosses_start, 'crosses_end': crosses_end})
    # 25 ms at 60 Hz; scale for the historical 30 Hz target so a normal
    # 33.3333 ms interval crossing a selection boundary remains conclusive.
    # Integer arithmetic avoids overflow when a valid budget is very large.
    whole_budget_ns = math.floor(budget_ns)
    boundary_tolerance_ns = max(25000000, (whole_budget_ns * 3 + 1) // 2)
    start_gap_ns = selected[0]['steady_ns'] - origin - start_ns if selected else None
    end_gap_ns = end_ns - (selected[-1]['steady_ns'] - origin) if selected and end_ns is not None else None
    values = [item['interval_ns'] for item in intervals]
    duration = sum(values) / 1e9
    issues, notes = [], []
    if not intervals: issues.append('fewer than two samples in selected window')
    if duration < minimum_seconds: issues.append('selected duration below requested minimum')
    if end_ns is not None and (not samples or samples[-1]['steady_ns'] - origin < end_ns):
        issues.append('capture ends before requested window is complete')
    if any(item['interval_ns'] > boundary_tolerance_ns for item in crossing_intervals):
        issues.append('interval crossing requested window boundary exceeds coverage tolerance')
    if start_gap_ns is not None and start_gap_ns > boundary_tolerance_ns:
        issues.append('requested window start lacks substantial sample coverage')
    if end_gap_ns is not None and end_gap_ns > boundary_tolerance_ns:
        issues.append('requested window end lacks substantial sample coverage')
    if expect_cache and metadata['cache_state'] != expect_cache:
        issues.append('declared cache state does not match expected state')
    if metadata['cache_state'] == 'unknown': issues.append('cold/warm cache state was not annotated')
    if metadata['overwritten_samples']:
        issues.append('bounded ring overwrote samples; complete trace coverage is unavailable')
        if metadata['cache_state'] == 'cold': issues.append('cold capture lost startup samples to bounded ring')
        notes.append('bounded ring overwrote older samples; startup/cold coverage is incomplete')
    if metadata['contention_drops']:
        issues.append('concurrent recording dropped samples; cadence evidence is incomplete')
        notes.append('concurrent recording dropped samples; intervals can include missing guest entries')
    notes.append('guest swap routine entry includes command preparation; this is not GPU completion or display presentation timing')
    notes.append('strict target-budget counts can include nanosecond quantization (for example 16,666,667 ns at 60 Hz); they do not prove a hitch or a missed display deadline; rounded reference thresholds do not replace the exact target budget')
    notes.append('original 20 Hz states and cinematics can produce legitimate 50 ms intervals; threshold counts do not identify defects')
    notes.append('cache state and scene are operator annotations, not inferred or independently verified')
    notes.append('window statistics count only fully contained intervals; crossing intervals are reported separately; coverage is inconclusive when a crossing interval or an uncovered edge exceeds max(25 ms, 1.5 target intervals), rounded to integer ns; this is a coverage check, not a hitch diagnosis')
    report = {'schema_version': 1, 'source': metadata['source'],
              'cache_state': metadata['cache_state'], 'scene': metadata.get('scene', 'unfiltered'),
              'sample_validation': {'sufficient': not issues, 'issues': issues,
                                    'minimum_seconds': minimum_seconds, 'duration_seconds': duration},
              'retention': {key: metadata[key] for key in ('capacity', 'total_samples', 'retained_samples', 'overwritten_samples', 'contention_drops')},
              'window': {'requested_start_seconds': start_seconds, 'requested_duration_seconds': window_seconds,
                         'first_sample_seconds': (selected[0]['steady_ns'] - origin) / 1e9 if selected else None,
                         'last_sample_seconds': (selected[-1]['steady_ns'] - origin) / 1e9 if selected else None,
                         'samples': len(selected), 'intervals': len(intervals),
                         'boundary_coverage': {
                             'policy': 'fully_contained_intervals_only; crossing_intervals_reported_separately',
                             'tolerance_ms': boundary_tolerance_ns / 1e6,
                             'start_gap_ms': start_gap_ns / 1e6 if start_gap_ns is not None else None,
                             'end_gap_ms': end_gap_ns / 1e6 if end_gap_ns is not None else None,
                             'crossing_intervals': crossing_intervals}},
              'notes': notes}
    report['cadence'] = {
        'target_fps': target_fps, 'budget_ms': budget_ns / 1e6,
        'observed_guest_swap_hz': None,
        'low_1_percent_hz': None, 'low_1_percent_mean_interval_ms': None,
        'low_1_percent_interval_count': 0,
        'low_1_percent_definition': '1000 / mean_ms of slowest ceil(interval_count / 100) intervals',
        'percentile_method': 'nearest_rank',
    }
    if values:
        tail_count = (len(values) + 99) // 100
        tail_mean_ms = sum(sorted(values, reverse=True)[:tail_count]) / tail_count / 1e6
        report['cadence'].update(
            observed_guest_swap_hz=len(values) / duration,
            low_1_percent_hz=1000 / tail_mean_ms,
            low_1_percent_mean_interval_ms=tail_mean_ms,
            low_1_percent_interval_count=tail_count)
        report['interval_ms'] = {'p50': percentile(values, .50) / 1e6,
                                 'p95': percentile(values, .95) / 1e6,
                                 'p99': percentile(values, .99) / 1e6,
                                 'p99.9': percentile(values, .999) / 1e6,
                                 'max': max(values) / 1e6}
        # Rounded reference thresholds are literal; the target and historical
        # 30 Hz thresholds retain their exact rate-derived budgets separately.
        thresholds = [('target_budget', budget_ns), ('16.6667ms', 16666700),
                      ('25ms', 25000000), ('33.3333ms', 33333300),
                      ('33.333333333333ms', 1e9 / 30), ('50ms', 50000000), ('100ms', 100000000)]
        report['strictly_over_threshold'] = {
            label: {'threshold_ms': ns / 1e6,
                    'interval_count': sum(value > ns for value in values),
                    'bursts': bursts(intervals, ns)} for label, ns in thresholds}
        report['largest_intervals'] = [{**item, 'interval_ms': item['interval_ns'] / 1e6}
                                       for item in sorted(intervals, key=lambda item: item['interval_ns'], reverse=True)[:10]]
    return report


def self_test():
    # Synthetic arithmetic/format checks only: these are never game results.
    timestamps = [0]
    for interval in [33333333] * 5 + [50000000] * 3 + [33333333] * 5:
        timestamps.append(timestamps[-1] + interval)
    samples = [{'type': 'sample', 'sequence': i, 'steady_ns': timestamp}
               for i, timestamp in enumerate(timestamps)]
    metadata = {'type': 'metadata', 'schema_version': 1, 'source': 'guest_swap_routine_entry',
                'clock': 'steady_clock', 'cache_state': 'cold', 'scene': 'unfiltered',
                'origin_ns': 0, 'capacity': 100, 'total_samples': len(samples),
                'retained_samples': len(samples), 'overwritten_samples': 0, 'contention_drops': 0}
    report = analyze(metadata, samples, minimum_seconds=0, expect_cache='cold')
    assert report['interval_ms'] == {'p50': 33.333333, 'p95': 50.0, 'p99': 50.0,
                                     'p99.9': 50.0, 'max': 50.0}
    assert report['cadence']['target_fps'] == 30
    assert report['cadence']['low_1_percent_hz'] == 20
    budget = report['strictly_over_threshold']['33.333333333333ms']
    assert budget['interval_count'] == 3 and budget['bursts']['longest_consecutive_intervals'] == 3
    assert budget['bursts']['largest_bursts'][0]['total_ms'] == 150
    assert report['strictly_over_threshold']['50ms']['interval_count'] == 0
    sixty = analyze(metadata, samples, minimum_seconds=0, target_fps=60)
    assert sixty['strictly_over_threshold']['25ms']['interval_count'] == 13
    assert report['sample_validation']['sufficient']
    assert not analyze(metadata, samples, minimum_seconds=30)['sample_validation']['sufficient']
    assert not analyze(metadata, samples, minimum_seconds=0, expect_cache='warm')['sample_validation']['sufficient']
    truncated = dict(metadata, capacity=4, overwritten_samples=len(samples) - 4, retained_samples=4)
    clipped = analyze(truncated, samples[-4:], minimum_seconds=0)
    assert clipped['retention']['overwritten_samples'] and 'overwrote' in clipped['notes'][0]
    bad = [dict(s) for s in samples]; bad[-1]['steady_ns'] = 0
    try: analyze(metadata, bad)
    except ValueError: pass
    else: raise AssertionError('nonmonotonic timestamps accepted')
    print('PASS synthetic 30 Hz intervals, 50 ms burst, cold/warm duration validation, ring truncation and invalid timestamps')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path, nargs='?')
    parser.add_argument('--start-seconds', type=float, default=0)
    parser.add_argument('--window-seconds', type=float)
    parser.add_argument('--minimum-seconds', type=float, default=30)
    parser.add_argument('--target-fps', type=float, default=30,
                        help='guest cadence target, e.g. 60 or 59.94 (default: historical 30 Hz; not display FPS)')
    parser.add_argument('--expect-cache', choices=('cold', 'warm'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test: self_test(); return 0
    if not args.trace: parser.error('trace path is required unless --self-test is used')
    try:
        metadata, samples = read_trace(args.trace)
        report = analyze(metadata, samples, start_seconds=args.start_seconds,
                         window_seconds=args.window_seconds, minimum_seconds=args.minimum_seconds,
                         expect_cache=args.expect_cache, target_fps=args.target_fps)
        result = json.dumps(report, indent=2, allow_nan=False) + '\n'
        if args.output: args.output.write_text(result, encoding='utf-8')
        else: sys.stdout.write(result)
        return 0 if report['sample_validation']['sufficient'] else 2
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'frame trace error: {error}\n')

if __name__ == '__main__':
    raise SystemExit(main())
