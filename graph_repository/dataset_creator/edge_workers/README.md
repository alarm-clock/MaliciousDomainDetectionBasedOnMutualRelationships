## How to create edge worker

Creating new edge worker is as simple as creating worker class inside this folder, nothing more, DatasetImporter
will find it, and it's declared options. But such class must fulfill few requirements:
- Must inherit from `graph_repository.dataset_creator.common.Worker` class
- Must have `worker_name` attribute does not collide with other workers
- Must declare options in `available_options` attribute that does not collide with other option is tuple\[ worker name,
  option name, arguments for that option or none]
- Must have at least 2 options, default one (default be new workers standard), and `"worker_name"_all` option that
  is used when all option is used as program argument. Therefore, if given worker creates multiple edge types, _all
  option should be the one that creates all edge types.
- Must implement method `_compute`
- In `graph_repository.dataset_creator.common.GraphTypes` add yours edge types and node types (if you don't just use domains)

Note that option name is then used in program arguments so make it understandable.