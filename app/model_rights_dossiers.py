"""Curated public evidence. Informational only: these records never grant rights.

An operator must still verify the exact checkpoint and deployment before enabling.
"""

DOSSIERS = {
    'bs-roformer-zfturbo': {
        'status': 'checkpoint_mit_training_data_review_required',
        'references': [
            'https://github.com/ZFTurbo/Music-Source-Separation-Training/issues/254#issuecomment-5914058767',
            'https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.12',
            'https://sigsep.github.io/datasets/musdb.html',
        ],
        'note': 'Code and exact v1.0.12 checkpoint are MIT per author confirmation, with ZFTurbo credit. '
                'The author explicitly leaves MUSDB18-HQ training-data conditions for deployment review. '
                'Only SHA-256 3e9daecd70aaed5b5a0d1f861cc4d77eaa45afb3fc6301b1cf32c1be0f5868fb is supported. '
                'Not BS RoFormer SW: those weights have unverified rights. Disabled until documented operator review.',
    },
    'uvr-kara-2': {
        'status': 'public_grant_scope_unconfirmed',
        'references': [
            'https://github.com/Anjok07/ultimatevocalremovergui#license',
            'https://github.com/TRvlvr/model_repo/releases/tag/all_public_uvr_models',
            'https://github.com/Anjok07/ultimatevocalremovergui/issues/2185',
        ],
        'note': 'Upstream general MIT statement; exact KARA 2 weight ownership and scope still disputed. No automatic activation.',
    },
    'drumsep-weights': {
        'status': 'checkpoint_rights_unconfirmed',
        'references': [
            'https://github.com/inagoy/drumsep',
            'https://github.com/inagoy/drumsep/issues/9',
            'https://huggingface.co/splitzo/drumsep',
            'https://github.com/openmirlab/mdxnet-infer',
            'https://github.com/inagoy/drumsep/issues/8',
            'https://github.com/inagoy/drumsep/blob/main/LICENSE',
            'https://github.com/openmirlab/mdxnet-infer/releases/tag/weights-drumsep-v1',
            'https://github.com/openmirlab/mdxnet-infer/blob/master/README.md',
        ],
        'note': '2026-10-20 evidence review: inagoy repository LICENSE is MIT for software, while the weight checkpoint was distributed separately; issue #9 specifically requests commercial weight rights without a definitive upstream grant. Splitzo model card labels its 335 MB ONNX MIT, but the converter cannot grant rights absent in source weights. Distinct aufr33/jarredou MDX23C 6-stem weights have SHA-256 verified independent mirrors but no original weight license; conflicting mirror tags are not author grants. Preserve disabled default; use licensed Mega 53/DSP functional alternatives. An operator attestation is not a substitute for the rights grant.',
    },
    'chordformer': {
        'status': 'five_checkpoints_unconfirmed',
        'references': ['https://github.com/mwaseemrandhawa/ChordFormer'],
        'note': 'Review each of the five weights and the exact MTA fork separately. BTC-HCQT/MTA refiners remain usable alternatives.',
    },
    'madmom': {
        'status': 'noncommercial_weights',
        'references': [
            'https://github.com/CPJKU/madmom/blob/main/LICENSE',
            'https://creativecommons.org/licenses/by-nc-sa/4.0/',
        ],
        'note': 'Original pretrained weights are CC BY-NC-SA 4.0; free_only inside a commercial hosted deployment is insufficient.',
    },
    'diffsinger-qixuan': {
        'status': 'restricted_free_service',
        'references': ['https://github.com/yqzhishen/qixuan-diffsinger/blob/main/terms_of_use/Terms_of_Use.zh-CN.md'],
        'note': 'Published terms restrict paid services; other voicebanks and vocoders need their own rights checks.',
    },
    'diffsinger-nishiren': {
        'status': 'individual_commercial_permission',
        'references': ['https://github.com/Gardanana/Nishiren-AI-Diffsinger/blob/main/terms-of-service.md'],
        'note': 'Commercial rights require author approval; an admin checkbox does not replace it.',
    },
    'diffsinger-spore': {
        'status': 'noncommercial_modified_terms',
        'references': ['https://github.com/knoxstation/SPORE'],
        'note': 'Model-specific modified NC/ND restrictions; commercial use not automatically permitted.',
    },
}
