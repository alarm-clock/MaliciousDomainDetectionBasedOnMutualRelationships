#!/bin/bash

if [[ $(whoami) != "root" ]]; then
  echo "Must run as root, exiting..."
  exit 1
fi

echo "Stopping neo4j service"
systemctl stop neo4j.service
echo "Dumping database into /var/lib/neo4j/import/neo4j.dump note that any existing neo4j.dump dump will be rewritten"
neo4j-admin database dump --overwrite-destination=true --to-path=/var/lib/neo4j/import neo4j
echo "Starting neo4j service"
systemctl start neo4j.service
echo "Started neo4j service, enjoy"