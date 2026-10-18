"""Provider-specific authentication presentation; never changes OAuth checks."""
from .auth import OAUTH_PROVIDERS

ICONS={'google':'google.png','facebook':'facebook.png','github':'github.svg'}


def buttons(providers):
    links=[]
    for item in providers:
        key=item.get('id')
        if key not in ICONS:continue
        label=OAUTH_PROVIDERS[key]['label']
        links.append(f'<a class="social-login social-{key}" href="/oauth/{key}/start"><img src="/static/social/{ICONS[key]}" width="20" height="20" alt="" aria-hidden="true"><span>Continua con {label}</span></a>')
    return '<div class="social-auth"><div class="auth-divider"><span>oppure</span></div>'+''.join(links)+'</div>' if links else ''


def registration_notice(provider,user,created):
    label=OAUTH_PROVIDERS[provider]['label']
    title=f'Registrazione con {label} completata' if created else f'Accesso con {label}: account in attesa'
    message=f'La registrazione con {label} è stata completata. ' if created else f'L’accesso con {label} è stato riconosciuto, ma il tuo account non è ancora attivo. '
    if user['email_confirmed']:
        message+='L’indirizzo email è già verificato. '
    else:
        message+=f'Conferma l’indirizzo email associato a {label} tramite il link di verifica. Se necessario, richiedine un altro dalla pagina di login. '
    message+='Il profilo resta disabilitato finché un amministratore non lo approva; riceverai una comunicazione quando sarà attivato.'
    return {'title':title,'message':message,'extra':''}
