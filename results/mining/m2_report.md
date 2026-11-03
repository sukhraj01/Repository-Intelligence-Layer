### Yield

| stage | count |
| --- | --- |
| repositories_listed | 200 |
| merged_prs | 190197 |
| prs_with_closing_issue | 23670 |
| pairs | 25422 |
| prs_mined_attempted | 2000 |
| prs_mined | 1391 |
| positives_total | 11047 |
| added_function_defs_total | 8695 |

Status of attempted pull requests: {"mined": 1391, "no_positive": 206, "no_python_change": 386, "quarantined": 17}
Quarantine reasons: {"changed_file_unparseable:mixed-tabs-spaces": 1, "changed_file_unparseable:python2-except": 3, "changed_file_unparseable:python2-long-literal": 2, "changed_file_unparseable:syntax-other": 1, "diff_truncated": 3, "old_file_missing_at_base": 4, "patch_missing": 3}

### Mined pull requests (one row per property)

| property | n | median | mean | p90 | max |
| --- | --- | --- | --- | --- | --- |
| positives_per_pr | 1391 | 2.0 | 7.942 | 17.0 | 324.0 |
| py_files_changed | 1391 | 2.0 | 4.584 | 9.0 | 103.0 |
| hunk_lines_touched | 1391 | 17.0 | 84.715 | 148.0 | 6433.0 |
| corpus_units | 1391 | 2685.0 | 13657.926 | 34027.0 | 630017.0 |

### Parse failures

Quarantined for an unparseable changed file: 7 of 2000 attempted (0.4%); by cause: {"mixed-tabs-spaces": 1, "python2-except": 3, "python2-long-literal": 2, "syntax-other": 1}. Unparsed files of mined corpora, by cause: {"mixed-tabs-spaces": 1, "python2-except": 208, "python2-exec": 2, "python2-long-literal": 6, "python2-octal": 29, "python2-print": 893, "syntax-other": 363}. Mined pull requests with at least one unparsed corpus file: 133 of 1391.

### Test-file positives (the pool has none)

3966 of 11047 corpus positives (35.9%) are in test files; 656 of 1391 mined pull requests have a test positive and 105 have only test positives.

### Links

Pairs 25422, issues 24849, pull requests with an issue 23670; issues with several pull requests 519; pull requests with several issues 1163; pull requests whose body names an issue the closing list lacks 5518; closing list cut at the limit 5; mined pairs with the issue edited after the pull request was created 63 of 1497 (4.2%).

### Selection by the published pool

1844 of 23670 linked pull requests of 200 repositories are in the published pool (7.8%); pool pull requests with no closing reference found: 661. Median per-repository kept share: 0.1471.

| property | kept n | dropped n | kept median | dropped median | difference | 95% interval | excludes 0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| corpus_units | 158 | 1233 | 800.5 | 3182.0 | -2381.5 | [-15849.0, -466.5] | True |
| hunk_lines_touched | 158 | 1233 | 39.0 | 15.0 | 24.0 | [16.0, 38.5] | True |
| positives | 158 | 1233 | 6.0 | 2.0 | 4.0 | [3.0, 7.0] | True |
| py_files_changed | 158 | 1233 | 4.0 | 2.0 | 2.0 | [1.0, 3.0] | True |
