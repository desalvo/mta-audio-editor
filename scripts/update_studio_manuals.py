#!/usr/bin/env python3
"""Idempotent IT/EN manual addendum for the actual MIDI/studio checkpoint."""
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONTENT = {
'en': {
'user': ['Advanced MIDI and AI studio checkpoint',
'Open the MIDI sidebar to create/import independent tracks, export multitrack MIDI, create a linked MIDI metronome or open its tempo graph. Sidebar state is saved for the current identity through lazy database patches.',
'Select multiple notes, move/resize them or use quantize, swing, humanize, split/join and transpose. Musical changes support undo/redo. The searchable paginated event list includes notes, CC, program, bend, pressure, SysEx and metadata. Controller lanes support CC, 14-bit bend, pressure and program events, shared zoom/scroll, group dragging, arrow keys, snap and undo/redo. Save MIDI before closing. The piano roll draws the visible viewport rather than allocating a full-length bitmap.',
'Import/export supports SMF0/1/2 and SMPTE 24/25/29.97/30. SMF2 retains independent pattern tempo maps; SMF0/1 preserve timestamps using the project grid. Combining independent patterns may require channel reassignment. UMP uses its lossless JSON export.',
'FluidSynth with the reviewed FluidR3 GM bank is an optional per-track instrument with program, bank, gain, polyphony and reverb. Missing instruments do not prevent MIDI editing. The bank and library require separate installation. A linked MIDI metronome follows marker/grid changes: unlink it before manually editing notes. The tempo graph edits decimal BPM through drag, arrows or double-click without stretching audio. Adaptive timing is read-only.',
'The MIDI sidebar opens AI Vocal Studio and Audio-to-MIDI. Select a MIDI melody for 2–8 editable harmony parts, or up to 32 independent pitched audio sources for Basic Pitch CPU transcription. Source clips, delay and region offsets are respected. Tabs expose source, parameters, execution and results. Close the window without cancelling; find the job in All jobs. Results are saved atomically when the project is unchanged; otherwise review and import explicitly. Retry can reuse unchanged completed sources. Singing synthesis is not available: authorized voicebanks, lyrics/phonemes, multimodel transcription, dedicated ASIO and complete hardware routing remain open. See docs/STUDIO_WORKFLOWS_R210_EN.md.'],
'admin': ['MIDI/GM and AI studio deployment checkpoint',
'Editor/sidebar/MIDI-device preferences are isolated by identity and written lazily to the existing database. Independent patches merge transactionally. Historical native settings are not all migrated. A visible selector does not prove hardware compatibility.',
'GM requires a dynamic FluidSynth library and the reviewed FluidR3 GM 3.1 bank (148,398,306 bytes). Operator overrides: MTA_FLUIDSYNTH_LIBRARY and MTA_GM_SOUNDFONT_DIR. The bank checksum is checked before use. FluidSynth and the bank carry separate LGPL/MIT licenses: preserve their notices. Third-party binaries and bank data are not bundled in this source archive.',
'In Studio models, explicitly accept the linked Basic Pitch licenses and install its separate Python 3.11/3.12 ONNX CPU runtime. A real inference test and checksum verification precede activation. Administrators can test again, disable/enable or uninstall the model; active jobs prevent removal. Configure the job timeout (default 3600 s) and intermediate-result retention (default seven days). ONNX telemetry is disabled before initialization. Queue admission, accounting and project permissions are reused. No ROCm/CUDA compatibility or GPU consumption is claimed for Basic Pitch. Authorized singing models remain unavailable.']},
'it': {
'user': ['MIDI avanzato e checkpoint dei moduli AI',
'Aprire la sezione MIDI della sidebar per creare/importare tracce indipendenti, esportare MIDI multitraccia, creare il metronomo MIDI collegato o aprire il grafico tempo. Lo stato della sidebar viene salvato per l’identità corrente nel database, con scritture differite.',
'Selezionare più note, trascinarle/ridimensionarle oppure usare quantizzazione, swing, humanization, split/join e trasposizione. Le modifiche musicali sono annullabili. La lista eventi ricercabile e paginata include note, CC, programmi, bend, pressione, SysEx e metadati. Le corsie controller supportano CC, bend a 14 bit, pressione e programmi, zoom/scroll condivisi, trascinamento di gruppo, frecce, snap e annulla/ripristina. Salvare il MIDI prima di chiudere. Il piano roll disegna la porzione visibile invece di allocare un’immagine per l’intero brano.',
'Import/export supportano SMF0/1/2 e SMPTE 24/25/29.97/30. SMF2 conserva le mappe tempo indipendenti; SMF0/1 mantengono i timestamp usando la griglia progetto. Unire pattern indipendenti può richiedere la riassegnazione dei canali. Per UMP usare l’esportazione JSON senza perdita.',
'FluidSynth con il banco FluidR3 GM verificato è uno strumento opzionale per traccia con programma, banco, gain, polifonia e riverbero. La sua assenza non impedisce l’editing MIDI. Banco e libreria richiedono installazione separata. Il metronomo MIDI collegato segue marker e griglia: scollegarlo prima dell’editing manuale. Il grafico tempo modifica i BPM decimali tramite trascinamento, frecce o doppio click, senza modificare la velocità audio. Il tempo adattivo è di sola lettura.',
'Dalla sidebar MIDI si aprono AI Vocal Studio e Audio-to-MIDI. Selezionare una melodia MIDI per 2–8 parti armonizzate modificabili, oppure fino a 32 sorgenti audio intonate indipendenti per la trascrizione Basic Pitch CPU. Clip, delay e offset della regione vengono rispettati. Le schede espongono sorgente, parametri, esecuzione e risultati. Chiudere la finestra non annulla il job, consultabile da Tutti i job. Il risultato viene salvato atomicamente se il progetto è invariato; altrimenti richiede revisione e importazione esplicita. Retry può riutilizzare sorgenti completate invariate. Il canto sintetico non è disponibile: restano voicebank autorizzati, lyrics/fonemi, trascrizione multimodello, ASIO dedicato e routing hardware completo. Riferimento: docs/STUDIO_WORKFLOWS_R210.md.'],
'admin': ['Checkpoint distribuzione MIDI/GM e moduli AI',
'Le preferenze editor/sidebar/dispositivi MIDI sono isolate per identità e scritte in modo differito nel database esistente. Patch indipendenti vengono unite in transazione. Non tutte le impostazioni native storiche sono migrate. Un selettore visibile non dimostra compatibilità hardware.',
'GM richiede una libreria FluidSynth dinamica e il banco FluidR3 GM 3.1 verificato (148.398.306 byte). Override operatore: MTA_FLUIDSYNTH_LIBRARY e MTA_GM_SOUNDFONT_DIR. Il checksum del banco viene verificato prima dell’uso. FluidSynth e banco hanno licenze LGPL/MIT separate: conservarne gli avvisi. Binari e dati del banco non sono inclusi nel sorgente.',
'Da Modelli Studio accettare esplicitamente le licenze collegate di Basic Pitch e installare il runtime separato Python 3.11/3.12 ONNX CPU. Un test reale di inferenza e il checksum precedono l’attivazione. Gli amministratori possono ripetere il test, abilitare/disabilitare e disinstallare il modello; i job attivi ne impediscono la rimozione. Sono configurabili timeout (default 3600 s) e conservazione intermedi (default sette giorni). La telemetria ONNX è disattivata prima della inizializzazione. Restano coda, accounting e permessi esistenti. Non viene dichiarata compatibilità ROCm/CUDA o consumo GPU per Basic Pitch. Modelli vocali autorizzati restano indisponibili.']}}


for role in ('user','admin'):
    CONTENT['en'][role].append('YourMT3 noPS is an additional operator-installed CPU backend for full-mix transcription into predicted GM/percussion parts. A real piano fixture passed through the queue and was saved as editable MIDI. This is not a ten-instrument accuracy benchmark. Velocity is generated; no calibrated confidence is reported. Installation, pinned hashes and licenses: docs/YOURMT3_RUNTIME_R210_EN.md. Vocal synthesis and multimodel reconciliation remain open.')
    CONTENT['it'][role].append('YourMT3 noPS è un backend CPU aggiuntivo installabile dall’operatore per trascrivere mix in parti GM/percussioni previste. Una prova reale di pianoforte è passata dalla coda ed è stata salvata come MIDI modificabile. Non è un benchmark di accuratezza su dieci strumenti. La velocity è generata; non viene indicata confidenza calibrata. Installazione, hash e licenze: docs/YOURMT3_RUNTIME_R210.md. Restano canto sintetico e riconciliazione multimodello.')
    CONTENT['en'][role].append('Native Audio devices / ASIO / routing selects the host API, physical devices, buffer and stereo-master/input matrices. The compiled callback does not call Python. A duplex stream supports playback and stereo recording. Physical ASIO certification, independent per-track hardware buses and the ASIO corresponding-source redistribution bundle remain open. Native Studio models use dedicated local API paths; remote AI workflows use the shared token and recover results without duplicate charges.')
    CONTENT['it'][role].append('Nelle app native, Dispositivi audio / ASIO / routing seleziona API, dispositivi fisici, buffer e matrici master stereo/ingresso. Il callback compilato non chiama Python. Uno stream duplex supporta riproduzione e registrazione stereo. Restano certificazione ASIO fisica, bus hardware indipendenti per traccia e bundle di sorgenti corrispondenti per ridistribuire ASIO. Modelli Studio usa API locali dedicate; i workflow remoti condividono il token e recuperano risultati senza doppi addebiti.')


def main():
    for lang, roles in CONTENT.items():
        for role, paragraphs in roles.items():
            path = ROOT/'app/docs'/(role+('-en' if lang=='en' else '')+'.html')
            soup = BeautifulSoup(path.read_text(), 'html.parser')
            if old := soup.find(id='r210-midi-studio'):
                old.decompose()
            for old in soup.select('.toc a[href="#r210-midi-studio"]'):
                old.decompose()
            section = soup.new_tag('section', id='r210-midi-studio')
            heading = soup.new_tag('h2')
            heading.string = ('34. ' if role=='user' else '22. ')+paragraphs[0]
            section.append(heading)
            for text in paragraphs[1:]:
                paragraph = soup.new_tag('p')
                paragraph.string = text
                section.append(paragraph)
            image_name='ai-vocal-midi-workflow.png' if role=='admin' else 'midi-controller-lanes.png'
            caption=('Workflow Studio e capacità MIDI effettive' if role=='admin' else 'Corsie controller MIDI: eventi condivisi e annullabili') if lang=='it' else ('Studio workflow and actual MIDI capabilities' if role=='admin' else 'MIDI controller lanes: shared editable events and undo/redo')
            figure=soup.new_tag('div',attrs={'class':'figure'})
            figure.append(soup.new_tag('img',src='/static/docs-assets/'+image_name,alt=caption))
            label=soup.new_tag('p');label.string=caption;figure.append(label);section.append(figure)
            soup.find(id='technical-appendix').insert_before(section)
            if toc := soup.select_one('.toc .cols'):
                link = soup.new_tag('a', href='#r210-midi-studio')
                link.string = heading.get_text()
                toc.append(link)
            path.write_text(str(soup))
    for path in [*(ROOT/'app/docs').glob('*.html'), ROOT/'scripts/manual_reference.py']:
        text = path.read_text().replace('Type 0/1 SMF up to 8 MiB.', 'SMF0/1/2 up to 8 MiB; PPQ and SMPTE timebases.').replace('SMF tipo 0/1 fino a 8 MiB.', 'SMF0/1/2 fino a 8 MiB; base tempi PPQ e SMPTE.')
        path.write_text(text)
    for lang in ['IT', 'EN']:
        path = ROOT/'docs'/('VST3_USER_GUIDE_'+lang+'.md')
        text = path.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if '8 MiB' in line and ('SMF' in line or 'tipo 0/1' in line):
                lines[i] = ('Use the MIDI sidebar to create/import independent MIDI tracks. SMF0/1/2 up to 8 MiB and PPQ/SMPTE timebases are supported. SMF2 retains independent tempo maps; SMF0/1 preserve event timing with the project grid. Existing audio is not retimed.' if lang=='EN' else 'Usare la sezione MIDI della sidebar per creare/importare tracce indipendenti. Sono supportati SMF0/1/2 fino a 8 MiB e basi tempi PPQ/SMPTE. SMF2 conserva le mappe tempo indipendenti; SMF0/1 mantengono il timing con la griglia progetto. L’audio esistente non cambia velocità.')
        text = '\n'.join(lines)+'\n'
        text = text.replace('Restano esclusi SMF tipo 2/SMPTE.', 'Sono supportati SMF tipo 2 e SMPTE.').replace('Asynchronous SMF type 2/SMPTE remain excluded.', 'SMF type 2 and SMPTE are supported.').replace('Le porte sono preferenze locali per utente/progetto.', 'Le porte sono preferenze DB per utente/progetto.').replace('Port selections are local to the user/project.', 'Port selections are DB preferences scoped to the user/project.')
        marker = '\n## '+('Optional General MIDI instrument' if lang=='EN' else 'Strumento General MIDI opzionale')
        text = re.sub(re.escape(marker)+r'[^\n]*\n.*?(?=\n## |\Z)', '', text, flags=re.S)
        text += marker+'\n\n'+('FluidSynth with the reviewed FluidR3 GM bank can be selected per track. Configure program, bank, gain, polyphony and reverb in instrument parameters. Install the optional library/bank separately and preserve their licenses. MIDI remains editable when they are missing. See AI_STUDIOS_IMPLEMENTATION_R210_EN for exact checksums and restrictions. The full AI studios and dedicated ASIO/hardware routing remain open.' if lang=='EN' else 'FluidSynth con il banco FluidR3 GM verificato è selezionabile per traccia. Configurare programma, banco, gain, polifonia e riverbero nei parametri. Installare separatamente libreria/banco opzionali e conservarne le licenze. Il MIDI rimane modificabile in loro assenza. Consultare AI_STUDIOS_IMPLEMENTATION_R210 per checksum e limiti. Moduli AI studio completi e ASIO/routing hardware restano aperti.')+'\n'
        # Keep operational instructions outside the license-only appendix.
        title='## Licenses and redistribution' if lang=='EN' else '## Licenze e distribuzione'
        optional=text[text.rindex(marker):]
        text=text[:text.rindex(marker)]
        at=text.index(title)
        text=text[:at]+optional+'\n'+text[at:]
        path.write_text(text)


if __name__ == '__main__':
    main()
