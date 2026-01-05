import hashlib                              #for hashing blocks 
import json                                 #to serialize blocks consistently 
from time import time                       #to time stamp blocks 
from urllib.parse import urlparse           #to validate node addresses 
from uuid import uuid4                      #to generate unique id for the node 

import requests                            #to communicate with other nodes for consensus 
from flask import Flask, jsonify, request #to create simple web API for interacting with the blockchain


class Blockchain:
    def __init__(self):
        self.chain = []                         #list of blocks 
        self.current_transaction = []           #list of pending transactions to be added to the next block 
        self.nodes = set()                      #set of registered nodes for consensus
        self.new_block(prev_hash=1, proof=100) #creates genesis block (the first block)


    #creates a new block with :
    def new_block(self, proof, prev_hash):  
        block = {
            "index": len(self.chain) + 1,                       #posistion in the chain 
            "timestamp": time(),                                #current time
            "transactions": self.current_transaction,           #list of pending transactions
            "proof": proof,                                     #result of the proof of work 
            "prev_hash": prev_hash or self.hash(self.chain[-1]),#hash of the previous block
        }
        self.current_transaction = []

        self.chain.append(block)                                #after adding a block the list of transactions is cleared
        return block

    # adds a new transaction to self.current_transaction
    def new_transaction(self, sender, recipient, amount):  
        self.current_transaction.append(
            {"sender": sender, 
             "recipient": recipient, 
             "amount": amount
             }
        )

        return self.last_block["index"] + 1         #returns the index of the block where this transaction will be added (the next block to be mined)
    

    # add a new node to the list of nodes
    def register_node(self, address):
        parsed_url = urlparse(address)

        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)

        elif parsed_url.path:
            self.nodes.add(parsed_url.path)

        else:
            raise ValueError("Invalid URL")
        
    # determine if a given block is valid
    def valid_chain(self, chain):  
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):                                                   #checking if a current_chain is valid
            block = chain[current_index]
            print(f"{last_block}")
            print(f"{last_block}")
            print("\n-----------------\n")

            last_block_hash = self.hash(last_block)
            if block["prev_hash"] != last_block_hash:
                return False

            if not self.valid_proof(last_block["proof"], block["proof"], last_block_hash):  #checking if proof of work is correct  
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f"http://{node}/chain")

            if response.status_code == 200:
                length = response.json()["length"]
                chain = response.json()["chain"]

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

            if new_chain:
                self.chain = new_chain
                return True

            return False

    @property
    def last_block(self):
        return self.chain[-1]
    

    def proof_of_work(self, last_block):
        last_proof = last_block["proof"]
        last_hash = self.hash(last_block)

        proof = 0

        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1

        return proof

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode() #hashing the block to ensure imutability

        return hashlib.sha256(block_string).hexdigest()

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):                #ensure the proof of work is met
        guess = f"{last_proof}{proof}{last_hash}".encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == "0000"


# API


app = Flask(__name__)

node_identifier = str(uuid4()).replace("-", "")

blockchain = Blockchain()


                                                                                #mines a block using POW 
@app.route("/mine", methods=["GET"])
def mine():
    last_block = blockchain.last_block
    proof = blockchain.proof_of_work(last_block)

    blockchain.new_transaction(sender="0", recipient=node_identifier, amount=1) #adds a reward transaction to the miner(1 coin)

    prev_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, prev_hash)

    response = {
        "message": "New Block Forged",
        "index": block["index"],
        "transactions": block["transactions"],
        "proof": block["proof"],
        "prev_hash": block["prev_hash"],
    }

    return jsonify(response), 200

                                                                            #accepts a new transaction
@app.route("/transactions/new", methods=["POST"])
def new_transaction():
    values = request.get_json()

    required = ["sender", "recipient", "amount"]

    if not all(k in values for k in required):
        return "Missing values", 400

    index = blockchain.new_transaction(values["sender"], values["recipient"], values["amount"]) #adds transaction to self.new_transaction

    response = {"message": f"transaction will be added to Block: {index}"}

    return jsonify(response), 201

                                                                                #returns full blockchain and its length
@app.route("/chain", methods=["GET"])
def full_chain():
    response = {"chain": blockchain.chain, "length": len(blockchain.chain)}

    return jsonify(response), 200


@app.route("/nodes/register", methods=["POST"])                         #registers a new node 
def register_nodes():
    values = request.get_json()

    nodes = values.get("nodes")

    if nodes is None:
        return "Error: Please supply a valid list of nodes ", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        "message": "New Nodes have been added",
        "total_nodes": list(blockchain.nodes),
    }

    return jsonify(response), 201


@app.route("/nodes/resolve", methods=["GET"])                                           #resolves conflicts using self.resolve_conflicts
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {"message": "Our chain was replaced", "new_chain": blockchain.chain}
    else:
        response = {"message": "Our chain is authoritative", "chain": blockchain.chain}

    return jsonify(response), 200                                                       #returns authorative chain


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument(
        "-p", "--port", default=5000, type=int, help="port to listen on"
    )
    args = parser.parse_args()
    port = args.port

    app.run(host="0.0.0.0", port=port)
