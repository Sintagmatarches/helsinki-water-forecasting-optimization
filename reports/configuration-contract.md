# Pipeline configuration contract

`ExperimentConfig` now validates its invariants at construction, before acquisition
or fitting: ISO months, ordered origins, positive horizons/step, development targets
ending no later than the final origin, final targets inside the observed window,
finite interval alpha in (0, 1), nonempty unique properties, finite nonnegative
optimization assumptions and a safe artifact directory name.

This prevents accidental holdout overlap or invalid resource assumptions through a
configuration edit. Tests exercise the real committed design and rejected designs.
The scientific `v1.0.0` configuration, model choices, numerical tolerance policy and
versioned evidence are unchanged. The new validation does not make arbitrary panel
sizes scientifically adequate or test-period reuse acceptable.

No scheduler, service tier, new model registry or orchestration dependency was added.
The existing CLI, source manifest, report command and CI reproduction are sufficient
for this small historical study. In a real recurring batch, version a new time window
and monitor acquisition freshness; do not describe a rerun of 2010–2018 as live water
operations. Code releases are identified by Git commit; evidence retains its original
scientific version and should not be relabelled to imply a new experiment.
