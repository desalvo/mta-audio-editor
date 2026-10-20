"""Shared bilingual technical appendices for online and PDF manuals.

Resource figures are planning estimates/formulas, never hardware certification.
"""
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def table(headers,rows):
    return '<table class="technical-table"><thead><tr>'+''.join('<th>'+escape(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def figure(name,caption):
    return '<figure class="figure"><img src="/static/docs-assets/r210/'+name+'" alt="'+escape(caption,quote=True)+'"><figcaption>'+escape(caption)+'</figcaption></figure>'


def appendix(lang):
    it=lang=='it'
    title='Appendici tecniche' if it else 'Technical appendices'
    parts=['<section class="technical-appendix" id="technical-appendix"><h2>'+title+'</h2><p>'+('Stato documentato: 0.3.0-r210. Le indicazioni di dimensionamento sono stime operative, non requisiti minimi certificati. I risultati locali non certificano dispositivi, plugin o server di produzione.' if it else 'Documented state: 0.3.0-r210. Sizing guidance is an operational estimate, not a certified minimum. Local results do not certify physical devices, plugins or production servers.')+'</p>']
    parts+=['<h3>A. '+('Tipi di applicazione e funzionalità' if it else 'Application types and capabilities')+'</h3>',table(['Tipo' if it else 'Type','Audio / DSP','AI','Plugin / MIDI'],[
        ['Web + server','Browser Web Audio; C++ DSP sul server' if it else 'Browser Web Audio; server C++ DSP','Coda globale server; token per client remoti' if it else 'Global server queue; tokens for remote clients','VST3 Linux sul server, editor remoto; Web MIDI ove supportato' if it else 'Server Linux VST3, remote editor; Web MIDI where supported'],
        ['Windows desktop','Motore corrente o C++; trasporto su dispositivo' if it else 'Current or C++; device transport','Motori locali oppure server remoto con token' if it else 'Local engines or token-authenticated remote server','VST3 Windows compatibili; MIDI nativo' if it else 'Compatible Windows VST3; native MIDI'],
        ['macOS desktop','Intel / Apple Silicon; corrente o C++' if it else 'Intel / Apple Silicon; Current or C++','Modelli locali o server; supporto acceleratore dipendente dal motore' if it else 'Local models or server; accelerator support depends on engine','Plugin macOS della stessa architettura; MIDI nativo' if it else 'Matching-architecture macOS plugins; native MIDI'],
        ['Linux desktop','Motore corrente o C++; dispositivo locale' if it else 'Current or C++; local device','CPU / CUDA / ROCm secondo runtime e hardware' if it else 'CPU / CUDA / ROCm depending on runtime and hardware','VST3 Linux, ALSA/MIDI secondo disponibilità' if it else 'Linux VST3; ALSA/MIDI subject to availability'],
        ['Android / iOS / iPadOS','Shell mobile, audio del browser/WebView' if it else 'Mobile shell; browser/WebView audio','Server; eventuali percorsi on-device solo con modello/runtime compatibile' if it else 'Server; on-device paths require a compatible model/runtime','Plugin sul server; MIDI browser secondo piattaforma' if it else 'Server-side plugins; browser MIDI depends on platform']])]
    parts+=['<h3>B. '+('Risorse e dimensionamento' if it else 'Resources and sizing')+'</h3>',table(['Profilo' if it else 'Profile','CPU / RAM','Disco / rete' if it else 'Disk / network','Note'],[
        ['Browser','4-8 GiB RAM del dispositivo: base di pianificazione' if it else '4-8 GiB device RAM: planning baseline','HTTPS; rete stabile per streaming e editor remoti' if it else 'HTTPS; stable network for streams and remote editors','Cache PCM 256 MiB; nessuna garanzia su WebView obsoleti' if it else '256 MiB PCM cache; no guarantee for obsolete WebViews'],
        ['Desktop / DSP','4 core / 8 GiB: punto di partenza, 16+ GiB per sessioni dense' if it else '4 cores / 8 GiB starting point; 16+ GiB for dense sessions','SSD consigliato; spazio per sorgenti, export e modelli' if it else 'SSD recommended; allow sources, exports and models','Plugin, frequenza e canali determinano il carico reale' if it else 'Plugins, sample rate and channel count determine actual load'],
        ['Server editor','4 vCPU / 8 GiB per test contenuti; dimensionare per concorrenza' if it else '4 vCPU / 8 GiB for small tests; size for concurrency','Volume persistente, backup, banda per sessioni simultanee' if it else 'Persistent volume, backups, bandwidth for concurrent sessions','Non è una capacità garantita per numero di utenti' if it else 'Not a guaranteed user capacity'],
        ['Server / desktop AI','16-32+ GiB RAM come budget iniziale; dipende dal modello' if it else '16-32+ GiB RAM initial budget; model dependent','Pesi e runtime separati: diversi GiB, talvolta decine' if it else 'Separate weights/runtimes: several GiB, sometimes tens','VRAM/unified memory e precisione dipendono dal modello; verificare ciascun motore' if it else 'VRAM/unified memory and precision depend on model; validate each engine'],
        ['Mobile','Memoria/CPU del browser; evitare progetti enormi' if it else 'Browser memory/CPU; avoid oversized projects','Wi-Fi stabile consigliato per audio e plugin remoti' if it else 'Stable Wi-Fi recommended for audio and remote plugins','Il DSP server non diventa locale sul telefono' if it else 'Server DSP does not become phone-local']])]
    parts+=[figure('pcm-budget-'+lang+'.svg','Memoria PCM teorica per minuto, stereo float32 (esclusi grafi, modelli e cache duplicate).' if it else 'Theoretical PCM memory per minute, stereo float32 (excluding graphs, models and duplicate caches).'),'<p><code>byte PCM = secondi × frequenza × canali × 4</code></p>' if it else '<p><code>PCM bytes = seconds × sample rate × channels × 4</code></p>']
    parts+=['<h3>C. '+('Limiti e comportamento' if it else 'Limits and behavior')+'</h3>',table(['Area','Limite / comportamento' if it else 'Limit / behavior'],[
        ['Progetto' if it else 'Project','44.1 / 48 / 96 kHz; frequenza fissa dopo la prima traccia. Timeline fino a 24 h.' if it else '44.1 / 48 / 96 kHz; sample rate fixed after first track. Timeline up to 24 h.'],
        ['Metronomo' if it else 'Metronome','Standard, zone con marker, adattivo. Pre-roll 0-64 battute; BPM griglia 20-400, anche decimali.' if it else 'Standard, marker zones, adaptive. Pre-roll 0-64 bars; grid BPM 20-400 including decimals.'],
        ['FX','Fino a 16 insert per catena; dipendenze e compatibilità VST3 da verificare per plugin.' if it else 'Up to 16 inserts per chain; validate dependencies and VST3 compatibility per plugin.'],
        ['MIDI','SMF tipo 0/1 fino a 8 MiB. UMP/MIDI 2.0 secondo driver/provider, non garantito per ogni dispositivo.' if it else 'Type 0/1 SMF up to 8 MiB. UMP/MIDI 2.0 depends on driver/provider, not guaranteed for every device.'],
        ['AI','Coda globale; limiti artefatti e timeout configurabili. Un modello installato non garantisce GPU compatibile.' if it else 'Global queue; configurable artifact limits and timeouts. An installed model does not guarantee GPU compatibility.'],
        ['Streaming C++','Buffer adattivo 0,35-1,2 s più blocco; non equivale a monitoring a latenza professionale garantita.' if it else 'Adaptive buffer 0.35-1.2 s plus block; not a guarantee of professional low-latency monitoring.'],
        ['Storage / billing','Default nuovi utenti 5 GiB; admin senza quota per default. Quote/crediti dipendono dal piano e dai permessi.' if it else 'New users default to 5 GiB; admins have no default quota. Quotas/credits depend on plan and permissions.']])]
    parts+=['<h3>D. '+('Prestazioni osservate e validazione' if it else 'Observed performance and validation')+'</h3>','<p>'+('Misure del precedente checkpoint locale: Chromium, otto tracce stereo da 30 s; carico e macchina di prova non equivalgono al server di produzione. I rapporti originali restano nella cartella validation del progetto.' if it else 'Measurements from the preceding local checkpoint: Chromium, eight 30-second stereo tracks; test machine and load do not represent the production server. Original reports remain in the project validation directory.')+'</p>',table(['Prova' if it else 'Test','Risultato osservato' if it else 'Observed result','Fonte locale' if it else 'Local source'],[
        ['C++ playback','Avvio 1,239 s; risposta fader 0,538 s; 0 underrun' if it else 'Start 1.239 s; fader response 0.538 s; 0 underruns','r210-continuous-pcm-browser.json'],
        ['C++ jitter / UI stalls','Ritardi rete fino a 180 ms, cinque stalli UI da 450 ms: 0 underrun' if it else 'Network delays up to 180 ms, five 450 ms UI stalls: 0 underruns','r210-continuous-pcm-stress.json'],
        ['Motore corrente' if it else 'Current engine','Avvio 2,198 s; riavvio con cache 0,265 s' if it else 'Start 2.198 s; cached restart 0.265 s','r210-continuity-current-engine.json']]),figure('execution-'+lang+'.svg','Dove avvengono elaborazione e uscita audio.' if it else 'Processing and audio output locations.'),'<p>'+('Certificazione ancora dipendente da prove sulla piattaforma reale: scheda audio, driver MIDI, plugin terzi, GPU e proxy. I consumi accettati sono contabilizzati; origine e validità restano nell’audit; il consumo zero non prova assenza di utilizzo GPU.' if it else 'Certification still depends on real-platform checks: audio interface, MIDI driver, third-party plugins, GPU and proxy. Accepted consumption is accounted; source and validity remain in the audit; zero consumption does not prove no GPU use.')+'</p></section>']
    return '\n'.join(parts)


def create_graphics():
    dest=ROOT/'app/static/docs-assets/r210';dest.mkdir(exist_ok=True)
    for lang in ('en','it'):
        title='Budget PCM stereo float32' if lang=='it' else 'Stereo float32 PCM budget'
        rows=''
        for y,rate in [(105,44100),(178,48000),(251,96000)]:
            value=rate*2*4*60/1024**2
            rows+=f'<text x="30" y="{y}" fill="#294965" font-size="18">{rate/1000:g} kHz</text><rect x="155" y="{y-26}" width="{value*9}" height="38" rx="5" fill="#1978b3"/><text x="{170+value*9}" y="{y}" fill="#15354e" font-size="17">{value:.2f} MiB/min</text>'
        (dest/f'pcm-budget-{lang}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 310"><rect width="760" height="310" rx="12" fill="#f1f7fc"/><text x="30" y="44" fill="#15354e" font-family="sans-serif" font-size="24">{title}</text><g font-family="sans-serif">{rows}</g></svg>')
        labels=['Browser / Mobile','DSP + AI sul server','Uscita nel browser','Desktop nativo','DSP + AI locale o remoto','Dispositivo audio locale'] if lang=='it' else ['Browser / Mobile','Server DSP + AI','Browser audio output','Native desktop','Local or remote DSP + AI','Local audio device']
        rows=''
        for index,label in enumerate(labels):
            col=index%3;row=index//3;x=20+col*245;y=76+row*138
            rows+=f'<rect x="{x}" y="{y}" width="225" height="74" rx="9" fill="{["#e4f1fb","#d9ecfa"][row]}" stroke="#75accb"/><text x="{x+112}" y="{y+42}" text-anchor="middle" font-size="{13 if len(label)>23 else 15}" fill="#163d58">{label}</text>'
            if col<2:rows+=f'<path d="M{x+227} {y+37}h16m-5-5 5 5-5 5" fill="none" stroke="#1978b3" stroke-width="2"/>'
        heading='Elaborazione e uscita audio' if lang=='it' else 'Processing and audio output'
        (dest/f'execution-{lang}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 320"><rect width="760" height="320" fill="#f5f9fc"/><g font-family="sans-serif"><text x="20" y="40" font-size="24" fill="#163d58">{heading}</text>{rows}</g></svg>')
