import os
import gc
import tempfile
import time

# Main code
import server
import shutil
import asyncio
import threading
import execution
import folder_paths
import importlib.util
from nodes import init_custom_nodes


def execute_prestartup_script():
    def execute_script(script_path):
        module_name = os.path.splitext(script_path)[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return True
        except Exception as e:
            print(f"Failed to execute startup-script: {script_path} / {e}")
        return False

    # node_paths = folder_paths.get_folder_paths("custom_nodes")
    # for custom_node_path in node_paths:
    #    possible_modules = os.listdir(custom_node_path)
    #    node_prestartup_times = []
    #    for possible_module in possible_modules:
    #        module_path = os.path.join(custom_node_path, possible_module)
    #        if os.path.isfile(module_path) or module_path.endswith(".disabled") or module_path == "__pycache__":
    #            continue
    #        script_path = os.path.join(module_path, "prestartup_script.py")
    #        if os.path.exists(script_path):
    #            time_before = time.perf_counter()
    #            success = execute_script(script_path)
    #            node_prestartup_times.append((time.perf_counter() - time_before, module_path, success))
    # if len(node_prestartup_times) > 0:
    #    print("\nPrestartup times for custom nodes:")
    #    for n in sorted(node_prestartup_times):
    #        if n[2]:
    #            import_message = ""
    #        else:
    #            import_message = " (PRESTARTUP FAILED)"
    #        print("{:6.1f} seconds{}:".format(n[0], import_message), n[1])
    #    print()


# execute_prestartup_script()

if __name__ == "__main__":
    if "CUBLAS_WORKSPACE_CONFIG" not in os.environ:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"


def prompt_worker(q, server):
    e = execution.PromptExecutor(server)
    last_gc_collect = 0
    need_gc = False
    gc_collect_interval = 10.0

    while True:
        timeout = None
        if need_gc:
            timeout = max(gc_collect_interval - (current_time - last_gc_collect), 0.0)

        queue_item = q.get(timeout=timeout)
        if queue_item is not None:
            item, item_id = queue_item
            execution_start_time = time.perf_counter()
            prompt_id = item[1]
            e.execute(item[2], prompt_id, item[3], item[4])
            need_gc = True
            q.task_done(item_id, e.outputs_ui)
            if server.client_id is not None:
                server.send_sync(
                    "executing",
                    {"node": None, "prompt_id": prompt_id},
                    server.client_id,
                )

            current_time = time.perf_counter()
            execution_time = current_time - execution_start_time
            print("Prompt executed in {:.2f} seconds".format(execution_time))

        if need_gc:
            current_time = time.perf_counter()
            if (current_time - last_gc_collect) > gc_collect_interval:
                gc.collect()
                last_gc_collect = current_time
                need_gc = False


async def run(server, address="", port=8188, verbose=True, call_on_start=None):
    await asyncio.gather(
        server.start(address, port, verbose, call_on_start), server.publish_loop()
    )


def cleanup_temp():
    temp_dir = folder_paths.get_temp_directory()
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    temp_dir = tempfile.mkdtemp(prefix="temp_", suffix="_path")
    print(f"Setting temp directory to: {temp_dir}")
    folder_paths.set_temp_directory(temp_dir)
    cleanup_temp()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = server.PromptServer(loop)
    q = execution.PromptQueue(server)

    init_custom_nodes()
    server.add_routes()
    threading.Thread(
        target=prompt_worker,
        daemon=True,
        args=(
            q,
            server,
        ),
    ).start()

    call_on_start = None

    def startup_server(address, port):
        import webbrowser

        if os.name == "nt" and address == "0.0.0.0":
            address = "127.0.0.1"
        webbrowser.open(f"http://{address}:{port}")

    call_on_start = startup_server

    try:
        loop.run_until_complete(
            run(
                server,
                address="0.0.0.0",
                port="9000",
                verbose=True,
                call_on_start=call_on_start,
            )
        )
    except KeyboardInterrupt:
        print("\nStopped server")

    cleanup_temp()
