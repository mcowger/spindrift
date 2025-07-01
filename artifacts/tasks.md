# Carvera CNC Protocol Re-implementation

**Scope:** Backend-only, no UI.
**Goal:** Rebuild an existing CNC protocol implementation. Its already in Python, but we want to make it properly modular. In general, we'd like to limit changes to the protocol implementation to the minimum necessary to get it working. However, we do want to remove all references and uses of the Kivy front end. Further, we'd like to refactor this into a library that can be used by other projects. I'll guide you along every step - take no action unless requested.
**General Instructions:**

- Don't write tests until specifically requested. Its more important to get things working than to test. We can always add tests later when we have full context.
- Focus on getting the basic communication working first. We can always add features later.
- Do not write documentation until specifically requested. We can always add docs later when we have full context.
- Avoiding writing new code for parsing GCODE, managing state or other common tasks where possible. Use existing libraries where possible, including those from pypi. Before writing extensive code for common tasks, prompt the user for other libraries to review.
- When using external libraries, priortize ones that have typescript definitions and types, as well as ones that are actively maintained and have a large user base.
- Records your progress and completions in a markdown file in artifacts/progress.md. Do not write README files at this time.

---

# Repo & Artifact Analysis

# Firmware & Controller and Protocol Research

- [ ] Review [`Carvera_Community_Firmware`](https://github.com/Carvera-Community/Carvera_Community_Firmware)
  - [ ] Identify modules handling: command parser, G-code processor, communication
  - [ ] Output: Directory map + 1–2 line summaries per relevant file/module
- [ ] Review [`Carvera_Controller`](https://github.com/Carvera-Community/Carvera_Controller)
  - [ ] Identify files/functions managing communication with the machine
  - [ ] List G-code/M-code command formatting patterns and response handling logic
- [ ] Parse [Smoothieware console commands](https://smoothieware.org/console-commands)
  - [ ] Extract all commands, categorize (M, G, Console)
  - [ ] For each command, extract: name, parameters, and response structure
  - [ ] Output: Structured JSON list of command definitions
- [ ] Parse [Makera supported codes](https://wiki.makera.com/en/supported-codes)
  - [ ] Extract custom commands and additions to Smoothieware
  - [ ] Identify unsupported or modified commands
  - [ ] Merge with Smoothieware data into a master command schema
- [ ] Parse traces from `artifacts/mockdata`
  - [ ] Extract command/response examples
  - [ ] Label by type: standard command, error response, edge case
  - [ ] Output: Sample dataset for testing in JSON format. Place in a file called artifacts/commands.json

---

# Protocol Mock Server ()

- [ ] One of the the first things done should be to create a basic server that pretends to operate like the real CNC machine.
- [ ] It should listen for commands on port 2222.
- [ ] It should respond to all queries with canned responses derived from the samples in artifacts/commands.json.
- [ ] It should reject concurrent connections.
- [ ] It should be able to handle multiple commands per connection.
- [ ] It should take at least 100ms to responds to each command.
- [ ] Do not implement this as a testing mock - use a real TCP server / IO implementation so that it can be used outside the context of tests.
- [ ] Review the file artifacts/commands.json. It contains structured information about the commands and responses. Use this to implement the mock server. Each entry is structured as following:

  "$#": { // The command
      "name": "name", // The name of the command
      "description": "description", // A description of the command
      "parameters": ["param1", "param2"], // The parameters the command takes
      "example": "$#", // An example of the command in use
  "response": "responsedata", // The response data, often multi-line. Sometimes the response is simply 'ok', especially for gcode
  "sends_ok": true, // Whether the command must sends an 'ok' response. If so, parsing of the output is not complete until the OK is received
  "modal": true, // Whether the command is modal (G codes only)
  "time_ms": 1000 // The time in ms that the command can take to execute. This can be used to establish command specific timeouts
  },

- [ ] Based on your review implement a server in python using third party libraries where possible. It should use the information from artifacts/commands.json to respond to commands.

---

# Mill Status Tracking and Modeling

- [ ] Create a class that can track the state of the mill, along with its actions. It should be called 'CNC' or similar.
- [ ] It should be able to handle position, feedrate, spindle speed, tool number, and other relevant state.
- [ ] It should be able to handle updates from the mock server.
- [ ] It should be able to handle updates from the real CNC machine.
- [ ] Use the information from artifacts/commands.json and artifacts/mockdata to understand the information available and how it is structured.
- [ ] Of key importantce is the ability to parse the status/? responses from the CNC machine and update the state of the mill accordingly.
- [  ] Parsing the status output ('?' command)
- [ ] You can review https://raw.githubusercontent.com/Carvera-Community/Carvera_Controller/refs/heads/main/carveracontroller/CNC.py for a good example of the kinds of data that should be stored in the class.   Don't just copy the code, but use it as a reference.
- When possible, use appropriately defined classes to store data (as an example, store position as a Position class, rather than a tuple of floats)
- [ ] Also review the parseAngleBracket function in https://raw.githubusercontent.com/Carvera-Community/Carvera_Controller/refs/heads/main/carveracontroller/Controller.py for guidance on how to parse the info responses and use them to update the instance variables of the CNC class.   Don't just copy the code, but use it as a reference.
- [ ] Do the same for the diagnose command with parseBigParentheses in the same file.
- At this point, do not implement any communication, just the methods and classes required to model the state of the mill and stub anything that communicates with the CNC machine.

---

# Protocol Implementation (TypeScript)

- [ ] Ensure that the CNCMachine class includes the required elements to connect to the CNC machine and send/receive commands.
- [ ] It should be able to handle the connection and disconnection of the CNC machine.
- [ ] It should be able to handle the sending and receiving of commands.
- [ ] It should be able to handle the queuing of commands to be sent to the CNC machine.
- [ ] It should be able to handle the retrying of commands that fail.
- [ ] It should be able to handle the timing of commands and responses.
- [ ] It should be able to handle the buffering of commands and responses.
- [ ] It should implement the background keep-alive functionality to prevent the CNC machine from timing out by sending status queries every 0.5 seconds (configurable).
- [ ] Maintain FIFO queue of outgoing commands
- [ ] Track pending commands and their expected responses
- [ ] Configurable retry limits and delays
- [ ] Gracefully handle unrecognized or malformed responses
- [ ] Notify on command completion, error, or async status updates

---

# High-Level Control API

- [ ] Implement high level control commands based on the lower level items below, derived from the commands and descriptions in `artifacts/commands.json` and https://wiki.makera.com/en/supported-codes

---

# Testing & Validation

- [ ] Develop end to end tests that run against the mock server to validate the protocol implementation.
- [ ] Develop end to end tests that run against the real CNC machine to validate the protocol implementation.
- [ ] For now, avoid unit tests of individual functions or compoenents.

---

# Documentation & Usage Examples

- [ ] Generate API documentation with Typedoc or similar
- [ ] Include interfaces, examples, and return types
- [ ] Write usage examples:
  - [ ] Moving the toolhead
  - [ ] Querying position
  - [ ] Sending raw or custom commands

---
