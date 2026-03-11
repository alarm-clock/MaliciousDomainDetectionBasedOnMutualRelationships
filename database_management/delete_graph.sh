#!/bin/bash

read -s -p "Enter database password: " pwd
echo

if [[ ! "$pwd" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Invalid password"
    exit 1
fi

cypher-shell -u neo4j -p "$pwd" "CALL apoc.periodic.iterate(\"MATCH (n)\",\"DETACH DELETE n\",{ batchSize: 10000, parallel: true }) YIELD batch RETURN 0"