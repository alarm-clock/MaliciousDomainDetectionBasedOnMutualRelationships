#!/bin/bash

jq -r '.[] | "\(.use) \(.path)"' $DATA_DIR/s_dataset_config.json | while IFS= read -r use path; do
  echo $path
  if [ "$use" = "true" ]; then
    echo Coping file $path	  
    cp $DATA_DIR/$path $SRATCHDIR
  fi
done

rm $SCRATCHDIR/dataset_config.json

jq '[.[] | select(.use == true)]' $DATA_DIR/s_dataset_config.json > $SCRATCHDIR/dataset_config.json
jq --arg p "$SCRATCHDIR" '.[] | .path = ($p + "/" + .path)' $SCRATCHDIR/dataset_config.json 



