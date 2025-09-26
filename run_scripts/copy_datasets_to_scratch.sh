#!/bin/bash

jq -r '.[] | "\(.use)|\(.path)"' $DATA_DIR/s_dataset_config.json | while IFS='|' read -r use path; do
  echo $path
  if [ "$use" = "true" ]; then
    echo Coping file $path	  
    cp $DATA_DIR/$path $SRATCHDIR
  fi
done

rm $SCRATCHDIR/dataset_config.json

jq '[.[] | select(.use == true)]' $DATA_DIR/s_dataset_config.json > $SCRATCHDIR/tmp.json
jq --arg p "$SCRATCHDIR" '.[] | .path = ($p + "/" + .path)' $SCRATCHDIR/tmp.json > $SCRATCHDIR/dataset_config.json

rm $SCRATCHDIR/tmp.json



