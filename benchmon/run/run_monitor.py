import signal

class RunMonitor:
    def __init__(self, args):
        self.should_run = True
        self.save_dir = args.save_dir
        self.prefix = args.prefix
        self.sampling_freq = args.sampling_freq
        self.checkpoint = args.checkpoint
        self.verbose = args.verbose

        # Setup SIGTERM handler for graceful termination
        signal.signal(signal.SIGTERM, self.terminate)

    def run(self):
        # run dool while OK
        pass

    def terminate(self):
        # kill dool process gracefully
        # postprocess data
        # terminate
        pass