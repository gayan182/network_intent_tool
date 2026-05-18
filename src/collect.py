import json
import yaml
from netmiko import ConnectHandler
import re

devices = [
    {"name": "lab-spine-01", "host": "172.20.20.3", "username": "admin", "password": "admin", "device_type": "arista_eos"},
    {"name": "lab-spine-02", "host": "172.20.20.5", "username": "admin", "password": "admin", "device_type": "arista_eos"},
    {"name": "lab-leaf-01",  "host": "172.20.20.2", "username": "admin", "password": "admin", "device_type": "arista_eos"},
    {"name": "lab-leaf-02",  "host": "172.20.20.4", "username": "admin", "password": "admin", "device_type": "arista_eos"},
]

def collect_bgp(device: dict):
    netmiko_device = device.copy()
    netmiko_device.pop("name", None)
    connection = ConnectHandler(**netmiko_device)
    # get router-id from plain text — more reliable
    plain_output = connection.send_command("show bgp summary")
    match = re.search(r"Router identifier (\S+),", plain_output)

    router_id = match.group(1) if match else None

    # get peers from JSON
    output = connection.send_command("show bgp summary | json")
    connection.disconnect()
    data = json.loads(output)


    bgp_data = {"vrfs": {}}                          # ← changed

    for vrf_name, vrf in data.get("vrfs", {}).items():
        print(f"VRF: {vrf_name} | routerId: {vrf.get('routerId')} | peers: {list(vrf.get('peers', {}).keys())}")


        vrf_dict = {                                  # ← changed
            "asn": vrf.get("asn"),
            "router_id": router_id,
            "neighbors": []
        }

        if vrf.get("peers"):
            for peer_ip, peer in vrf.get("peers", {}).items():
                if peer_ip == router_id:
                    continue
                vrf_dict["neighbors"].append({        # ← changed
                    "ip": peer_ip,
                    "remote_asn": peer.get("peerAsn"),
                    "state": peer.get("peerState"),
                })

        bgp_data["vrfs"][vrf_name] = vrf_dict        # ← changed

    return bgp_data

def collect_ospf(device: dict):
    netmiko_device = device.copy()
    netmiko_device.pop("name", None)
    connection = ConnectHandler(**netmiko_device)

    #get ospf neighbors from json
    output = connection.send_command("show ip ospf neighbor | json")
    connection.disconnect()
    data = json.loads(output)

    ospf_data = {"vrfs": {}}                          # ← changed

    for vrf_name, vrf in data.get("vrfs", {}).items():
        vrf_dict = {
            "instances": {}
        }
        if vrf.get("instList"):
            for instance, neighbor in vrf.get("instList", {}).items():
                instance_dict = {
                    "neighbors": []
                }
                for peer in neighbor.get("ospfNeighborEntries",[]):
                    instance_dict["neighbors"].append({
                        "neighbor_ip" : peer.get("routerId"),
                        "interface" : peer.get("interfaceName"),
                        "state" : peer.get("adjacencyState"),
                        "area" : peer.get("details",{}).get("areaId")
                    })
                    
                vrf_dict["instances"][instance] = instance_dict
            
            ospf_data["vrfs"][vrf_name] = vrf_dict    
     # ← changed

    return ospf_data




all_devices = {"devices": {}}

for device in devices:
    print(f"collecting from {device["name"]}......")
    bgp_data = collect_bgp(device)
    ospf_data = collect_ospf(device)
    all_devices["devices"][device["name"]] = {
        "bgp": bgp_data,
        "ospf": ospf_data
    }

# save to YAML
with open("current/bgp.yaml", "w") as f:
    yaml.dump(all_devices, f, default_flow_style=False)

print("Done - saved to current/bgp.yaml")
