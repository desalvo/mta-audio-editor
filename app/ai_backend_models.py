"""Model identifiers shared by local and queued server adapters."""
LEAD_BACKING_MODELS = [
    {"id": "uvr_mdxnet_kara_2", "filename": "UVR_MDXNET_KARA_2.onnx", "display_name": "UVR-MDX-NET Karaoke 2", "engine": "MDX", "quality": "balanced", "recommended": True},
    {"id": "mvsep-mega53", "filename": "operator-provided.ckpt", "display_name": "MVSep Mega 53 (Lead / Back Vocals)", "engine": "BS-RoFormer (external MSST)", "quality": "experimental", "recommended": False},
    {"id": "mel_roformer_karaoke_aufr33", "filename": "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", "display_name": "Mel-RoFormer Karaoke Aufr33/Viperx", "engine": "RoFormer", "quality": "high", "recommended": False},
    {"id": "mel_roformer_karaoke_gabox_v2", "filename": "mel_band_roformer_karaoke_gabox_v2.ckpt", "display_name": "MelBand RoFormer Karaoke Gabox V2", "engine": "RoFormer", "quality": "high", "recommended": False},
]
