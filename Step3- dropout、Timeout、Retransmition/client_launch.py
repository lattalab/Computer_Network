import subprocess
import sys
def launch_clients(HOST, PORT, num_clients, tasks_per_client):
    processes = []
    for i in range(num_clients):
        if len(tasks_per_client[i]) != 0:
            tasks = tasks_per_client[i]
            print(f"Launching client {i+1} with tasks: {tasks}")
            cmd = ['python', 'client.py', HOST, str(PORT)] + tasks
            processes.append(subprocess.Popen(cmd))
        else:
            print(f"No tasks provided for client {i+1}")
            continue

    # Wait for all processes to complete
    for process in processes:
        process.wait()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)
    else:
        HOST = sys.argv[1]  # The server's IP address given by argv[1]
        PORT = int(sys.argv[2]) # The server's port number given by argv[2]
        num_clients = int(input("Enter the number of clients to launch: "))
        tasks_per_client = []

        for i in range(num_clients):
            tasks = input(f"Enter tasks for client {i+1} (separated by dot): ").split(',')
            tasks_per_client.append(tasks)

        launch_clients(HOST, PORT, num_clients, tasks_per_client)