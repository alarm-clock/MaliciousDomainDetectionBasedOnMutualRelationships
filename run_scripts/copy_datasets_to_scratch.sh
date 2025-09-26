#!/bin/bash

jq -r '.[] | "\(.use) \(.path)"' $DATA_DIR/dataset_config.json | while IFS= read -r use path; do
  if [ "$use" = "true"]; then
    cp "$DATA_DIR$path" $SRATCHDIR
  fi
done

rm $SCRATCHDIR/dataset_config.json

jq '[.[] | select(.use == true)]' $DATA_DIR/dataset_config.json > $SCRATCHDIR/dataset_config.json
jq --arg p "$SCRATCHDIR" '.[] | .path = ($p + .path)' $SCRATCHDIR/dataset_config.json



