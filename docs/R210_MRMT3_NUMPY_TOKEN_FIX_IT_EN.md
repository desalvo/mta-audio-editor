# MR-MT3 NumPy token serialization / Serializzazione dei token NumPy MR-MT3

IT: Il runtime MR-MT3 su GPU AMD/ROCm ha superato la fase del modello ma il runner tentava `.cpu()` su un `numpy.ndarray`. Il runner converte ora sia `numpy.ndarray` sia tensori PyTorch in liste di ID interi non negativi, con controllo di dimensionalità, tipo e lunghezza. 15 test mirati superati. Occorre ripetere la prova sulla GPU reale; qualità e accuratezza 10–16 strumenti non certificate. L’output precedente non è stato salvato a causa dell’errore.

EN: Real AMD/ROCm MR-MT3 reached result serialization but the runner called `.cpu()` on a `numpy.ndarray`. The runner now accepts NumPy integer arrays and Torch integer tensors, validates shape/dtype/length and stores nonnegative token IDs. 15 targeted tests passed. Real GPU rerun, full-length inference, and 10–16-instrument accuracy remain unverified.
