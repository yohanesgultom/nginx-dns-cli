import click
import json
import shutil
import subprocess
import os
from urllib import request

CLOUDFLARE_TOKEN = os.getenv('CLOUDFLARE_TOKEN')
CLOUDFLARE_ZONE = '4a5f0497ea189f6b301fae78cb64ea83'
CLOUDFLARE_API_URL = f'https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE}/dns_records'
NGINX_HOME = '/etc/nginx'

@click.group()
def cli():
    pass

@cli.command()
@click.argument('domain')
def create_reverse_proxy(subdomain, domain, target_ip, target_port):
    # update cloudflare dns record
    click.echo(f'Updating CloudFlare DNS record...')
    payload = {
        "type":"A",
        "name": subdomain + '.' + domain,
        "content":target_ip,
        "ttl":1,
        "proxied":False
    }
    req = request.Request(CLOUDFLARE_API_URL, method='POST', data=bytes(json.dumps(payload), encoding='utf-8'))
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {CLOUDFLARE_TOKEN}')
    res = request.urlopen(req)
    click.echo(res.read())

    # update nginx config
    nginx_conf_file = os.path.join(NGINX_HOME, 'sites-available', subdomain)
    click.echo(f'Copying Nginx config file: {nginx_conf_file}...')
    shutil.copyfile('nginx.example.conf', nginx_conf_file)
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
def delete_reverse_proxy():
    click.echo('Dropped the database')

if __name__ == '__main__':
    cli()