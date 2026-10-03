# data/

Small, versioned inputs only (prompts, claim sets, labelled statements). This folder is pushed to the pod by
`pod/push.sh`, so keep it light. Large datasets are downloaded straight onto the pod volume by `pod/bootstrap.sh`.
For each dataset record: source, licence, and the exact download command or commit.
