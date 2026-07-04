#!/bin/bash

if [[ $(whoami) != "root" ]]; then
  echo "Must run as root, exiting..."
  exit 1
fi

echo "Stoping neo4j service"
systemctl stop neo4j.service

echo "Loading database from dump"
neo4j-admin database load --overwrite-destination=true --from-path=/var/lib/neo4j/import/ neo4j

echo "Setting permissions to relevant files"
chown -R neo4j:neo4j /var/lib/neo4j/data/databases/neo4j
chown -R neo4j:neo4j /var/lib/neo4j/data/transactions/neo4j

echo "Restored database from /var/lib/neo4j/import/neo4j.dump"
systemctl start neo4j.service
echo "Started neo4j server, enjoy"

