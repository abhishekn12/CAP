import os
import threading
import time
import requests
from flask import Flask, request, jsonify

# --- Basic Setup ---
app = Flask(__name__)

# In-memory key-value store
data = {}
data_lock = threading.Lock()

# Get the ID of this node from environment variables (set in docker-compose)
# Fallback for local testing
NODE_ID = os.environ.get('NODE_ID', 'local')

# Define the other nodes in the cluster. In a real system, this would be
# managed by a discovery service.
PEER_NODES = ['node1', 'node2', 'node3']
PEER_URLS = {node: f"http://{node}:5000" for node in PEER_NODES if node != NODE_ID}


# --- Helper Functions ---

def replicate_write(key, value):
    """
    Asynchronously sends a write operation to all peer nodes.
    This is used for eventual consistency.
    """
    payload = {'key': key, 'value': value}
    for node_url in PEER_URLS.values():
        try:
            # We don't wait for a response, just fire and forget.
            requests.post(f"{node_url}/replicate", json=payload, timeout=0.5)
            app.logger.info(f"Replication request sent to {node_url} for key '{key}'")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Failed to replicate to {node_url}: {e}")


def replicate_write_synchronous(key, value):
    """
    Synchronously sends a write to peer nodes and waits for acknowledgements.
    This is used for strong consistency.
    Returns the number of successful acknowledgements.
    """
    payload = {'key': key, 'value': value}
    success_count = 0

    def send_request(url, results):
        try:
            response = requests.post(f"{url}/replicate", json=payload, timeout=2)
            if response.status_code == 200:
                results.append(True)
                app.logger.info(f"Sync replication to {url} for key '{key}' SUCCEEDED.")
            else:
                app.logger.warning(
                    f"Sync replication to {url} for key '{key}' FAILED with status {response.status_code}.")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Could not connect to {url} for sync replication: {e}")

    threads = []
    results = []
    for node_url in PEER_URLS.values():
        thread = threading.Thread(target=send_request, args=(node_url, results))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    return len(results)


# --- API Endpoints ---

@app.route('/kv', methods=['POST'])
def handle_write():
    """
    Handles writing a key-value pair.
    The consistency level is determined by a query parameter.
    ?consistency=strong -> Strong Consistency
    ?consistency=eventual (or omitted) -> Eventual Consistency
    testing
    """
    try:
        write_data = request.get_json()
        key = write_data.get('key')
        value = write_data.get('value')
        if not key or value is None:
            return jsonify({"error": "Missing key or value"}), 400
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    consistency = request.args.get('consistency', 'eventual')

    if consistency == 'strong':
        # --- Strong Consistency Logic ---
        app.logger.info(f"Received STRONG write for key '{key}'")

        # We need a majority to agree. In a 3-node cluster, that's 2 nodes.
        # Since this node is one, we need 1 other peer to acknowledge.
        quorum = 1

        acks = replicate_write_synchronous(key, value)

        if acks >= quorum:
            with data_lock:
                data[key] = value
            app.logger.info(f"Quorum achieved for key '{key}'. Write committed.")
            return jsonify({"status": "success", "message": "Write committed with strong consistency"}), 200
        else:
            app.logger.error(f"Could not achieve quorum for key '{key}'. Only {acks} acks received.")
            return jsonify({"status": "error", "message": "Could not achieve quorum."}), 503  # Service Unavailable

    else:
        # --- Eventual Consistency Logic ---
        app.logger.info(f"Received EVENTUAL write for key '{key}'")
        with data_lock:
            data[key] = value

        # Replicate to other nodes in the background
        thread = threading.Thread(target=replicate_write, args=(key, value))
        thread.start()

        return jsonify({"status": "success", "message": "Write accepted"}), 200


@app.route('/kv/<key>', methods=['GET'])
def handle_read(key):
    """Handles reading a value by its key from the local store."""
    app.logger.info(f"Received READ for key '{key}'")
    with data_lock:
        if key in data:
            return jsonify({"key": key, "value": data[key]})
        else:
            return jsonify({"error": "Key not found"}), 404


@app.route('/replicate', methods=['POST'])
def handle_replication():
    """Internal endpoint for receiving replicated writes from peers."""
    try:
        replication_data = request.get_json()
        key = replication_data.get('key')
        value = replication_data.get('value')

        with data_lock:
            data[key] = value

        app.logger.info(f"Replicated write successful for key '{key}'")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Replication failed: {e}")
        return jsonify({"error": "Invalid replication data"}), 400


@app.route('/status', methods=['GET'])
def get_status():
    """Endpoint to check the node's status and current data."""
    return jsonify({
        "node_id": NODE_ID,
        "data": data
    })


if __name__ == '__main__':
    # Note: For production, use a proper WSGI server like Gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True)