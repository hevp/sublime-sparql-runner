Sublime SPARQL Runner
=====================

A Sublime Text 2/3 plugin to run SPARQL queries directly inside Sublime Text.

Based on the original [SPARQL Runner package](https://github.com/cezarsa/sublime-sparql-runner) by [cezarsa](https://github.com/cezarsa).

Functionality
-------------

* Runs current selected text or complete query in tab using currently selected endpoint
* Results of successful queries will be displayed in a separate tab.
* Multiple endpoints can be defined
* For any endpoint optionally basic authentication details can be provided
* Optional parameters can be defined for any endpoint

Installation
------------

* Use Sublime Package Control to install it (or clone it inside your Packages dir);

Usage
-----

* To select the current one open the command palette and choose `SPARQL: Select or add/edit endpoint` and then select the endpoint
* To add a new or edit an existing endpoint open the command palette and choose `SPARQL: Select or add/edit endpoint` -> `Add new or edit existing endpoint...`:
    * Provide the following values:
        * Unique name for endpoint (if name already in use you will be prompted to edit that endpoint)
        * URL for endpoint
        * Username (optional, leave empty to skip)
        * Password (optional)
        * Parameter name (optional, leave empty to skip)
        * Parameter value (optional)
    * Multiple parameters can be added by simply repeating the name and value prompts
* To run a query choose `SPARQL: Run query`. SPARQL Runner will run the query against the current endpoint. It will consider either the **selected text** or the **entire file** as the SPARQL query.

If you want to add a key binding to run queries, open your "Default.sublime-keymap" and add:

    [
      { "keys": ["super+shift+k"], "command": "run_sparql" }
    ]


Configuration
-------------

A typical configuration file looks as follows:

```
{
    "current": "dbpedia",
    "endpoints":
    {
        "my_sparql_endpoint":
        {
            "parameters":
            {
                "format": "CSV",
                "lang": "sparql"
            },
            "password": "<password>",
            "url": "<url>",
            "username": "<user>"
        },
        "dbpedia":
        {
            "url": "http://dbpedia.org/sparql"
        }
    }
}
```

* Further config options can be found in `Preferences` -> `Package Settings` -> `SPARQL Runner` -> `Settings`
