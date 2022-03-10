from copy import deepcopy

from ...schema import X509_FILE_MODE
from ..base.converter import BaseConverter
from .schema import schema

openvpn_definitions = {'properties': {}}
for definition in ['tunnel', 'client', 'server']:
    if definition != 'client':
        d = schema['definitions'][definition]['properties']
    else:
        d = schema['definitions'][definition]['allOf'][1]['properties']
    openvpn_definitions['properties'].update(deepcopy(d))


class OpenVpn(BaseConverter):
    netjson_key = 'openvpn'
    intermediate_key = 'openvpn'
    _schema = openvpn_definitions

    def to_intermediate_loop(self, block, result, index=None):
        vpn = self.__intermediate_vpn(block)
        result.setdefault('openvpn', [])
        result['openvpn'].append(vpn)
        return result

    def __intermediate_vpn(self, config, remove=[False, 0, '']):
        skip_keys = ['script_security', 'remote']
        delete_keys = []
        # allow server_bridge to be empty and still rendered
        if config.get('server_bridge') == '':
            config['server_bridge'] = True
        for key, value in config.items():
            if key in skip_keys:
                continue
            # mark keys which contain falsy values
            # usually not useful in the openvpn configuration format
            if value in remove:
                delete_keys.append(key)
        # delete config keys which are not needed (marked previously)
        for key in delete_keys:
            del config[key]
        # reformat remote list in order for simpler handling in template
        if 'remote' in config:
            remote = ['{host} {port}'.format(**r) for r in config['remote']]
            config['remote'] = remote
        # do not display status-version if status directive not present
        if 'status' not in config and 'status_version' in config:
            del config['status_version']
        config = self.__add_tls_auth_key(config)
        return self.sorted_dict(config)

    def __add_tls_auth_key(self, config):
        tls_auth = config.get('tls_auth', None)
        if not tls_auth:
            return config
        tls_auth = tls_auth.strip()
        if len(tls_auth.split(' ')) == 2:
            # The field already contains path to auth key
            # and TLS Auth direction. No operation is required.
            pass
        else:
            # The TLS Auth key is present in the field.
            # Determine TLS Auth key file path from CA's file path.
            ca_path = config.get('ca', '')
            dev = config.get('dev', '')
            tls_auth_path = '/'.join(ca_path.split('/')[:-1] + [f'{dev}_tls_auth.key'])
            if config.get('mode') == 'server':
                tls_auth_direction = 0
            else:
                tls_auth_direction = 1
            config['tls_auth'] = f'{tls_auth_path} {tls_auth_direction}'
            # Add TLS Auth key file
            file_data = {
                'path': tls_auth_path,
                'mode': X509_FILE_MODE,
                'contents': tls_auth,
            }
            try:
                self.netjson['files'].append(file_data)
            except KeyError:
                self.netjson['files'] = [file_data]
        return config

    def to_netjson_loop(self, block, result, index):
        vpn = self.__netjson_vpn(block)
        result.setdefault('openvpn', [])
        result['openvpn'].append(vpn)
        return result

    def __netjson_vpn(self, vpn):
        vpn = self.type_cast(vpn, openvpn_definitions)
        if vpn.get('server_bridge') is True:
            vpn['server_bridge'] = ''
        if 'remote' in vpn:
            remote = []
            for r in vpn['remote']:
                host, port = r.split()
                remote.append(dict(host=host, port=int(port)))
            vpn['remote'] = remote
        return vpn
