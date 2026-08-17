# Bolt PID attribution and licensing

RangeLab EV does not claim to have reverse-engineered Chevrolet Bolt parameter
identifiers. Community work makes exported Bolt telemetry possible and must be
credited without silently relicensing it as MIT code.

## Relevant community sources

- Sean Graham's [Chevy Bolt OBD2 PIDs project](https://allev.info/boltpids/)
  documents logging workflows, uncertainty markers, and a collaboratively
  maintained list.
- Chris Meier's [ChevyBoltPIDs repository](https://github.com/mr23/ChevyBoltPIDs)
  contains a modified list and credits the original work.
- The repository's
  [PID license](https://github.com/mr23/ChevyBoltPIDs/blob/main/LICENSE) states
  CC BY-NC-SA 2.5 CA and non-commercial use terms.

Those terms are not the same as this project's MIT license. RangeLab EV
therefore does not bundle, copy, or redistribute that complete PID definition
table. Users may import CSV logs produced by their own separately configured
tools. Column-alias compatibility implemented as original interoperability code
does not make RangeLab EV the source of the underlying PID discoveries.

## Rules for future contributors

Before adding a PID formula, table, sample, or converted vendor file:

1. Identify the original source and its actual license.
2. Confirm the proposed use is permitted, including commercial and
   share-alike restrictions.
3. Preserve attribution and modification notices.
4. Keep third-party data in an explicitly licensed location with a notice that
   it is not covered by the root MIT license.
5. Do not describe an uncertain community signal as manufacturer-verified.

When permission is unclear, link to the source and let the user supply their
own export instead of copying the material.

## Data quality caveat

The community documentation itself flags some signals and formulas as unknown,
broken, or still needing validation. RangeLab should allowlist only signals
needed for a feature, retain unit/source metadata, test plausible ranges, and
show missing/uncertain data rather than fabricate a clean reading.

This page records an engineering precaution, not legal advice.
