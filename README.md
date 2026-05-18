# network_intent_tool


┌─────────────────────────────────────────────────────┐
│  Network Intent Verification Tool                   │
│  v1 — Complete Spec                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  LAB                                                │
│  Platform:   Containerlab                           │
│  Dev nodes:  Arista cEOS (free, fast, Cisco-like)   │
│  Target:     Cisco IOS (real devices)               │
│  Topology:   4 nodes — 2 spine, 2 leaf              │
│                                                     │
│  PROTOCOLS                                          │
│  BGP:        iBGP + eBGP                            │
│  OSPF:       single area to start                   │
│                                                     │
│  GAP TYPES (exactly 5)                              │
│  1. BGP peer wrong state (Idle/Active)              │
│  2. BGP peer missing entirely                       │
│  3. BGP attribute mismatch                          │
│     (send-community, timers, RR-client)             │
│  4. OSPF neighbour down                             │
│  5. OSPF cost or timer mismatch                     │
│                                                     │
│  STATE                                              │
│  Source of truth: collect on healthy lab            │
│                   → becomes intended YAML           │
│  Current state:   collect before every run          │
│  Schema:          shared — Arista + Cisco           │
│                   normalised into same format       │
│                                                     │
│  PARSING                                            │
│  Arista:     vtysh/EOS | json → json.loads()        │
│  Cisco IOS:  show cmd → Genie parser → dict         │
│  Both:       normalise → identical YAML schema      │
│                                                     │
│  AGENT                                              │
│  Framework:  LangGraph — 3 nodes                    │
│              detect → investigate → report          │
│  Max tools:  5 show commands per gap                │
│  Tools:      6 investigation + 2 fix tools          │
│                                                     │
│  8 TOOLS                                            │
│  1. check_reachability                              │
│  2. get_bgp_neighbor_detail                         │
│  3. get_ospf_neighbor_detail                        │
│  4. get_interface_state                             │
│  5. get_running_config                              │
│  6. conclude                                        │
│  7. push_fix_command  (NAPALM, whitelisted)         │
│  8. verify_fix        (re-collect + re-compare)     │
│                                                     │
│  FIXING                                             │
│  Level:      human in the loop                      │
│  Flow:       generate → diff → approve → push       │
│              → verify → report                      │
│  Safety:     command whitelist enforced             │
│              NAPALM rollback if verify fails        │
│                                                     │
│  INTERFACE                                          │
│  MCP server: FastMCP                                │
│  Client:     Claude Desktop                         │
│  MCP tools:  get_lab_status                         │
│              detect_gaps                            │
│              investigate_gap                        │
│              get_remediation                        │
│              run_show_command                       │
│                                                     │
│  TECH STACK — 100% Python                           │
│  Netmiko  NAPALM  Genie  LangGraph                  │
│  Anthropic SDK  FastMCP  PyYAML                     │
│                                                     │
├─────────────────────────────────────────────────────┤
│  OUT OF SCOPE v1                                    │
│  Ansible, pyATS, web UI, production devices         │
│  auto-remediation without approval                  │
│  ISIS, MPLS, EIGRP, other protocols                 │
│  historical trending, multi-site                    │
├─────────────────────────────────────────────────────┤
│  SUCCESS CRITERIA                                   │
│  Given a lab with deliberate breaks:                │
│  tool detects all 5 gap types correctly             │
│  agent runs show commands autonomously              │
│  identifies correct root cause with evidence        │
│  generates exact fix commands                       │
│  engineer approves → pushed → verified closed       │
│  all via Claude Desktop MCP interface               │
└─────────────────────────────────────────────────────┘

-----------LAB Setup Device Logins---------------------

╭──────────────────────────────┬────────────────┬─────────┬───────────────────╮
│             Name             │   Kind/Image   │  State  │   IPv4/6 Address  │
├──────────────────────────────┼────────────────┼─────────┼───────────────────┤
│ clab-intent-lab-lab-leaf-01  │ ceos           │ running │ 172.20.20.4       │
│                              │ ceos:4.36.0.1F │         │ 3fff:172:20:20::4 │
├──────────────────────────────┼────────────────┼─────────┼───────────────────┤
│ clab-intent-lab-lab-leaf-02  │ ceos           │ running │ 172.20.20.2       │
│                              │ ceos:4.36.0.1F │         │ 3fff:172:20:20::2 │
├──────────────────────────────┼────────────────┼─────────┼───────────────────┤
│ clab-intent-lab-lab-spine-01 │ ceos           │ running │ 172.20.20.5       │
│                              │ ceos:4.36.0.1F │         │ 3fff:172:20:20::5 │
├──────────────────────────────┼────────────────┼─────────┼───────────────────┤
│ clab-intent-lab-lab-spine-02 │ ceos           │ running │ 172.20.20.3       │
│                              │ ceos:4.36.0.1F │         │ 3fff:172:20:20::3 │
╰──────────────────────────────┴────────────────┴─────────┴───────────────────╯

When power off everyday after work : 
# destroys the lab cleanly
sudo containerlab destroy -t ~/network-intent-tool/lab/topology.yaml

When come back tomorrow : 
# bring it back up
cd ~/network-intent-tool
sudo containerlab deploy -t lab/topology.yaml

--------------LAB Network Design----------------------------

spine01 (AS65001)  ──── spine02 (AS65001)
        10.0.0.1                10.0.0.2
           |    \              /    |
           |      \          /      |
        leaf01     \        /     leaf02
        (AS65001)   \      /      (AS65001)
        10.0.0.3     \    /       10.0.0.4
                   (iBGP full mesh)

OSPF runs on all links — carries loopback reachability
BGP runs on top — uses loopbacks as update-source

Node          Loopback        
─────────────────────────────
lab-spine-01  10.0.0.1/32     
lab-spine-02  10.0.0.2/32     
lab-leaf-01   10.0.0.3/32     
lab-leaf-02   10.0.0.4/32     

Point-to-point links:
spine01 ↔ leaf01    10.1.1.0/30
spine01 ↔ leaf02    10.1.2.0/30
spine02 ↔ leaf01    10.1.3.0/30
spine02 ↔ leaf02    10.1.4.0/30
spine01 ↔ spine02   10.1.5.0/30

