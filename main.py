import click
import json
import shutil
import subprocess
import os
from urllib import request, error

CLOUDFLARE_TOKEN = os.getenv('CLOUDFLARE_TOKEN')
CLOUDFLARE_ZONE = os.getenv('CLOUDFLARE_ZONE')
CLOUDFLARE_API_URL = f'https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE}/dns_records'
NGINX_HOME = '/etc/nginx'

@click.group()
def cli():
    pass

@cli.command()
@click.argument('subdomain')
@click.argument('domain')
@click.argument('target_ip')
@click.argument('target_port')
def create_reverse_proxy(subdomain, domain, target_ip, target_port):
    """Create new reverse proxy SUBDOMAIN.DOMAIN pointing to TARGET_IP (internally to TARGET_PORT).

    SUBDOMAIN Subdomain name excluding the domain name eg. subdomain
    DOMAIN Domain name eg. domain.com (will make subdomain.domain.com)
    TARGET_IP IPv4 address eg. 1.1.1.1
    TARGET_PORT Internal port set in Nginx eg. 8080
    """    
    # update cloudflare dns record
    try:
        click.echo(f'Updating CloudFlare DNS record...')
        payload = {
            "type":"A",
            "name": subdomain,
            "content":target_ip,
            "ttl":1,
            "proxied":False
        }
        req = request.Request(CLOUDFLARE_API_URL, method='POST', data=bytes(json.dumps(payload), encoding='utf-8'))
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {CLOUDFLARE_TOKEN}')
        res = request.urlopen(req)
        click.echo(res.read())
    except error.HTTPError as e:
        click.echo(message='Update failed: maybe record has already existed', err=True)

    # update nginx config
    try:
        nginx_conf_file = os.path.join(NGINX_HOME, 'sites-available', subdomain)
        click.echo(f'Copying Nginx config file: {nginx_conf_file}...')
        shutil.copyfile('nginx.template.conf', nginx_conf_file)
        with open(nginx_conf_file, 'r') as f:
            data = f.read()
            data = data.replace('{{server_name}}', subdomain + '.' + domain)
            data = data.replace('{{port}}', str(target_port))
        with open(nginx_conf_file, 'w') as f:
            f.write(data)
        cmd = f'cd {NGINX_HOME}/sites-enabled && sudo ln -s ../sites-available/{subdomain}'
        click.echo(f'Running: {cmd}')
        os.system(cmd)
        cmd = f'sudo service nginx restart'
        click.echo(f'Running: {cmd}')
        os.system(cmd)
    except Exception as e:
        click.echo(message=str(e), err=True)

    # update letsencrypt certificate
    click.echo(f'Updating LetsEncrypt certificate...')
    cmd = f'sudo certbot --nginx --cert-name {domain}'
    sp = subprocess.Popen('sudo certbot certificates | grep Domains', shell=True, stdout=subprocess.PIPE)
    spout = sp.stdout.read().decode('utf-8')
    for token in spout.split():
        token = token.strip()
        if token.endswith(domain):
            cmd += f' -d {token}'
    cmd += f' -d {subdomain}.{domain}'
    click.echo(f'Running: {cmd}')
    os.system(cmd)

@cli.command()
@click.argument('subdomain')
@click.argument('domain')
def delete_reverse_proxy(subdomain, domain):
    """Create new reverse proxy SUBDOMAIN.DOMAIN pointing to TARGET_IP (internally to TARGET_PORT).

    SUBDOMAIN Subdomain name excluding the domain name eg. subdomain
    DOMAIN Domain name eg. domain.com (will make subdomain.domain.com)
    """    
    # update letsencrypt certificate
    click.echo(f'Updating LetsEncrypt certificate...')
    cmd = f'sudo certbot --nginx --cert-name {domain}'
    sp = subprocess.Popen('sudo certbot certificates | grep Domains', shell=True, stdout=subprocess.PIPE)
    spout = sp.stdout.read().decode('utf-8')
    for token in spout.split():
        token = token.strip()
        if (not token.startswith(subdomain)) and token.endswith(domain):
            cmd += f' -d {token}'
    cmd += f' -d {subdomain}.{domain}'
    click.echo(f'Running: {cmd}')
    os.system(cmd)
    # TODO delete cloudflare
    # TODO delete nginx conf

if __name__ == '__main__':
    cli()