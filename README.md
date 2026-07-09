# User Manual

This is the user manual for the system for domain maliciousness evaluation based on mutual relationships with other domains.
## Prerequisites

While Python is a multiplatform scripting language, the system was tested solely on Linux, specifically Ubuntu 22.04.5 LTS.
Therefore, just to be sure, I will say that ```Linux OS``` is a prerequisite, but technically, it can be run anywhere Python can be
executed. An internet connection is also a must because dependencies must be downloaded before starting the program. Next prerequisite is:
- ```Python version 3.10``` and ,
- ```Python virtual enviroment``` to manage system dependencies,
- ``pip`` version ``24.3.1`` or newer.

The system also uses ```Neo4j``` database with: 
- kernel version ```2026.02.2``` and newer, 
- and Cypher version ```5``` and newer,
- ```Apoc``` extension with version ```2026.01.4``` and newer. 

For ```Mapoc``` extension (developed as part of this system) compilation, you need:
- ``Java openjdk 21.0.10``
- ``Apache Maven 3.6.3``


Optionally, you can use a ``MongoDb`` database for easier initial graph creation from the dataset. Without it, you need to create the graph, only using the graph edit API endpoints.

## Build
### System
First, you must create a Python virtual environment and activate it with the command:

```bash
python -m venv .venv
source .venv/bin/activate 
```
and then you install requirements using command:
```bash
pip install -r requirements.txt
```
Now the system should be able to run. Optionally, you can create a Singularity container from the TODO.def file and run the system inside it. For how to work with singularity containers, see their official tutorials.
Mapoc is being built simply using the command:
```bash
mvn clean package
```
inside Mapoc's main source code folder. This will create ``mapoc-1.0-SNAPSHOT.jar``, which needs to be put into Neo4j's ``plugins`` directory (usually ``/var/lib/neo4j/plugins``)
before startup. If you do it after startup, then you need to restart the Neo4j service so that the plugin can be loaded.

## Database

Neo4j database can run on a separate server other then main system (of course). It is best to give it as much memory as possible, especially if you plan to host a large domain relationship graph. You can also use the Neo4j tools to calculate optimal memory allocation for your graph size. Also, in its configuration, set pre-allocated memory to be equal max memory for faster performance. That is because every heap resize in Java calls the garbage collector unnecessarily, which slows down the database.

For multi-instance system deployment, it is also good to create multiple users for each instance with different read/write permissions on the graph. Note that this is not possible on the community edition, on which you have only one default user.
It is good to create three user types: a user who can freely read and write, a user who can only read, and a user who can work with temporary domains, maintenance nodes, and all relationship types. The first user is, for instance, who can fully edit the graph. The second user is for instances that only execute readonly queries. Last user is for instances
that evaluated domains but do not edit the graph as an additional layer of security. Only one system instance can edit the graph at a time. Usage of multiple instances for graph editing will result in a broken graph. Therefore, instances that do not edit the graph should start in mode without editing endpoints. To create these users, you can use these Cypher queries:
```
//first user
CREATE ROLE full_rw;

GRANT ACCESS ON DATABASE neo4j TO full_rw;
GRANT MATCH {*} ON GRAPH neo4j TO full_rw;
GRANT WRITE ON GRAPH neo4j TO full_rw;

CREATE USER full_rw_user
SET PASSWORD 'strong_password_1'
CHANGE NOT REQUIRED;

GRANT ROLE full_rw TO full_rw_user;

//second user
CREATE ROLE read_only;

GRANT ACCESS ON DATABASE neo4j TO read_only;
GRANT MATCH {*} ON GRAPH neo4j TO read_only;

CREATE USER read_only_user
SET PASSWORD 'strong_password_2'
CHANGE NOT REQUIRED;

GRANT ROLE read_only TO read_only_user;

//third user
CREATE ROLE restricted_tmp_writer;

GRANT ACCESS ON DATABASE neo4j TO restricted_tmp_writer;
GRANT MATCH {*} ON GRAPH neo4j TO restricted_tmp_writer;

GRANT CREATE RELATIONSHIP {*} ON GRAPH neo4j TO restricted_tmp_writer;
GRANT DELETE RELATIONSHIP {*} ON GRAPH neo4j TO restricted_tmp_writer;
GRANT SET PROPERTY {*} ON GRAPH neo4j RELATIONSHIP * TO restricted_tmp_writer;

DENY CREATE ON GRAPH neo4j NODE * TO restricted_tmp_writer;
DENY DELETE ON GRAPH neo4j NODE * TO restricted_tmp_writer;
DENY SET PROPERTY {*} ON GRAPH neo4j NODE * TO restricted_tmp_writer;

GRANT CREATE ON GRAPH neo4j NODE Tmp_domain TO restricted_tmp_writer;
GRANT DELETE ON GRAPH neo4j NODE Tmp_domain TO restricted_tmp_writer;
GRANT SET PROPERTY {*} ON GRAPH neo4j NODE Tmp_domain TO restricted_tmp_writer;

GRANT CREATE ON GRAPH neo4j NODE GraphVersion TO restricted_tmp_writer;
GRANT DELETE ON GRAPH neo4j NODE GraphVersion TO restricted_tmp_writer;
GRANT SET PROPERTY {*} ON GRAPH neo4j NODE GraphVersion TO restricted_tmp_writer;

GRANT CREATE ON GRAPH neo4j NODE NodeIdCnt TO restricted_tmp_writer;
GRANT DELETE ON GRAPH neo4j NODE NodeIdCnt TO restricted_tmp_writer;
GRANT SET PROPERTY {*} ON GRAPH neo4j NODE NodeIdCnt TO restricted_tmp_writer;

GRANT CREATE ON GRAPH neo4j NODE Tmp_domain_free_node_id_lock TO restricted_tmp_writer;
GRANT DELETE ON GRAPH neo4j NODE Tmp_domain_free_node_id_lock TO restricted_tmp_writer;
GRANT SET PROPERTY {*} ON GRAPH neo4j NODE Tmp_domain_free_node_id_lock TO restricted_tmp_writer;

GRANT CREATE ON GRAPH neo4j NODE Tmp_domain_free_node_id TO restricted_tmp_writer;
GRANT DELETE ON GRAPH neo4j NODE Tmp_domain_free_node_id TO restricted_tmp_writer;
GRANT SET PROPERTY {*} ON GRAPH neo4j NODE Tmp_domain_free_node_id TO restricted_tmp_writer;

CREATE USER restricted_tmp_user
SET PASSWORD 'strong_password_3'
CHANGE NOT REQUIRED;

GRANT ROLE restricted_tmp_writer TO restricted_tmp_user;
```

## Usage

After building and downloading all dependencies, you can start the system instance.

### Initial Graph Creation

Optionally, before starting, you can build an initial graph from the domain dataset that is stored in MongoDB. Supported data format is:

```json
{
    "domain_name": "gymlm.sk",
    "node_id": 42,
    "label": "benign",
    "dns": {
        "A": ["192.168.1.1", "42.42.42.42"],
        "AAAA": ["fe80::1234"],
        "CNAME": "some.hosting.com"
        ...
    },
    "ip_data": [{"ip": "67.67.67.67", ...}],
 ...
}
```
where a benign domain is a domain that has a benign substring in the label, all other domains are considered malicious. Node_id is unique node id that each domain must have otherwise they can not be parsed by the system. Dns, ip_data, and fields inside them are optional and can be omitted.

This import then can be done using command:
```bash
python3.10 -m main --neo_db path_to_neo_conf.json --mongo_db path_to_mongo_conf.json [-l logfile.log -ll LOGLEVEL] import_db --neo -e all [-r start1,end1,start2,end2,...]
```
where ``-r`` can be used to pick only domain that are within start,end range (including start and end), -l is for optional logging
and -ll is log level (default is info, can be set to debug), Neo4j configuration looks like this:

```json
{
      "host": "localhost",
      "port": 7687,
      "user": "neo4j",
      "pwd": "heslo",
      "db": "neo4j",
      "batch_delay": 1.0,
      "batch_size": 10000
}
```
where it is best to leave batch_size and batch_delay in default values for optimal performance. MongoDB configuration 
looks like this:
```json
{
	"client" : "localhost",
	"port" : 27017,
	"db" : "datasets",
	"collection" : "thousand"
}
```
that has its fields self explanatory.

If you don't want to build initial graph like this you still need before start do:
```bash
python3.10 -m main --neo_db path_to_neo_conf.json  import_db --empty
```
to create empty instance of domain relationship graph. Without this step system cannot work.
### Starting System Instance

Before you start instance, you must fill in the example configuration file that is in `config.json` file. In it, you must set
your Neo4j database data, you can set max number of workers (max_evaluations) that evaluate domains and max number of
(max_metapath2vec_evaluations) which can be used to limit number of evaluation workers that can evaluate domains using
Metapath2vec model concurrently. This can be used if you don’t have enough RAM or CPU power to ease system requirements for RAM and CPU.
Default values should be very safe on 64GB RAM systems and 16-core CPUs. Also, k-hop_neigh_params should be left default, and eval_params should be left default. Edit these only after you read my master’s thesis, so understand what these values do.
Also, you can set result_removal_time after which unclaimed evaluation results are deleted. Then you need to set your host, port, pwd_hash (sha256 hash of password), and auth_header_name (name of HTTP authentication header that will be checked)
for authentication when using the system's API, and lastly, you can set a deployment option. Those are:
- all - all endpoints are visible
- graph_repository - only graph editing endpoints
- evaluation -  only evaluation endpoints
- read_and_eval - domain evaluation and read-only queries endpoints
- read - only read-only query endpoint
- read_and_graph_repository - graph editing and read-only query endpoints
Optionally you can add or remove cert_file and key_file which are used if you want to use TLS, if you don't you can remove them.

Now you can start system instance using command:
```bash
python3.10 -m main --config path_to_confing.json server
```

Instance can be stopped using ``ctrl-c``/kill signal. 
### Containers (Singularity/Docker)

In folder containers you can find files for creating Singularity and Docker images that already have all prerequisites
installed and system is in ready-to-use state. Both Docker and Singularity images have two files to create image from:
one with only system and one with both system and Neo4j database within them. In both cases if you need to use VPN like 
Wireguard sometimes it is hard or impossible to execute it on hosting system or inside container so all containers
come with preinstalled ``proxychains`` to cheat system with "router" machine on which you can use VPN and to which you
can SSH (for example Metacentrum batch jobs). 


To build Singularity container firstly you must download Singularity on your machine. Then you can build image using 
command: 
```bash 
sudo singularity build name_of_image.sif containers/singularity/pick_your_file.def
```
Image must be built from 
main folder due to path restrictions. Then with created `.sif` image you can write simple bash script that will execute
anything you want. Note that Singularity container does not need to contain code within and can serve as only ready-made environment for fast development. You use code inside your own file 
system and you execute it inside. Like for example: ```singularity exec python3 -m main --config path/to/conf.json server```.

Docker API image is built from the repository root. The image uses a multi-stage
CPU-only build and expects Neo4j to run separately:
```bash
docker build -f containers/Docker/Dockerfile -t graph_repo .
```

The API image intentionally does not install DGL/GPU dependencies. This is
enough for graph CRUD/read endpoints used by Thor, but not for
evaluation/metapath2vec or runtime graph recalculations. That path likely needs
a separate GPU/DGL image or Compose profile, because the NVIDIA base image is
multi-GB, tied to CUDA/runtime compatibility, and hard to keep portable in dev
containers.

Created image is then started like this:
```bash
sudo docker run -v "$(pwd)/path/to/your/config":/workspace/app/config:ro -v "$(pwd)/path/to/log":/workspace/app/log graph_repo
```
This command will start container and system within it. Of course, if you edit image name or something else you must 
start container accordingly. Also, if you want to start system with proxychains or in different manner you must do it
using interactive session or any other way.

Config templates may be mounted into `/workspace/app/config-templates` as
`*.template` files. The Docker entrypoint renders them with environment
variables into `/workspace/app/config` before starting the application.

Before starting an empty development database for the first time, run:
```bash
python3 -m main --neo_db path_to_neo_conf.json import_db --empty
```

If you use the all-in-one Dockerfile with bundled databases, you must bind the
database directories into the container. The separate Neo4j container setup is
preferred for development and compose usage.

### API

API documentation can be read after system started on http(s)://host:port/docs for further information.

System API works as follows. For graph editing there are endpoints: 
- add,
- delete,
- update,

to which you can send domain data to be added, updated, or deleted. Data is passed as `application/json` with format:
```json
{
  "domains": [
    {
      "domain_name": "gymlm.sk",
      "node_id": 42,
      "label": "benign",
      "dns": {
        "A": ["192.168.1.1", "42.42.42.42"],
        "AAAA": ["fe80::1234"],
        "CNAME": "some.hosting.com",
        ...
        },
      "ip_data": [{"ip": "67.67.67.67", ...}],
      ...
    },
    ...
  ]
}
```

If you are deleting domains you can just pass `domain_name` inside domain data JSON body. Domain data format is taken 
from Hranický et al. "A Dataset of Information (DNS, IP, WHOIS/RDAP, TLS, GeoIP) for a Large Corpus of Benign, Phishing, and Malware Domain Names 2024".
In request headers it is also required to have header specified in system configuration (`auth_header_name`) with
pre shared secret that is hashed in the configuration as SHA256 hash. In response to edit request you will find
`job_id` which can be used to check edit progress. To do so you use `/job_status/<job_id>` endpoint.

Because of Neo4j free version not having any database or user management essentially you only have one user that can 
both read and edit graph. If you want to force readonly queries you can use `/read_query` endpoint to which you will pass
you query and data in `application/json` format:

```json
{
  "query": "UNWIND ids AS id MATCH (n: Domain {node_id: $id}) RETURN COUNT n AS domain_count",
  "data": {
    "ids": [42,69,55]
  }
}
```

If you want to use domain evaluation than for it there is one endpoint `evaluate`. Here you just submit domain and optionally
timeout again in `application/json` format: 

```json
{
  "domain": "gymlm.sk"
}
```
System will then return evaluation id that can be used to retrieve evaluation result using `/evaluate/<evaluation_id>` endpoint.
