# -*- coding: utf-8 -*-
"""
generate acquisition table with given template
"""

import collections
import os
import io
import platform
import subprocess
import jinja2
import yaml
import json
import shutil


def system_path():
    path = os.environ['PATH']
    return [x for x in path.split(';' if platform.system() == 'Windows' else ':') if x]


def lookup_file(name, path):
    for p in path:
        p = os.path.join(p, name)
        if os.path.isfile(p):
            return p
    return None


def tex_front_matter(stream, leader='%', surround='% ---'):
    if isinstance(stream, str):
        stream = io.StringIO(stream)
    max_line_length = 1000
    buffer = []
    leader_len = len(leader)
    in_front = False
    for line in stream:
        line = line.rstrip()
        if line == surround:
            if in_front:  # end
                in_front = False
                break
            else:  # start
                in_front = True
        elif in_front and line.startswith(leader):
            buffer.append(line[leader_len: ])
        else:
            raise ValueError('invalid line: `{}`'.format(line))
    if in_front:
        raise ValueError('missing end tag `{}`'.format(surround))
    return '\n'.join(buffer)


def update_mapping(orig_dict, new_dict):
    for k, o in orig_dict.items():
        n = new_dict.get(k, {})
        if isinstance(o, collections.Mapping):
            update_mapping(o, n)
            new_dict[k] = n
        else:
            new_dict[k] = o
    return new_dict


class XeLaTex:

    def __init__(self, bin='xelatex'):
        self.PATH = system_path()
        self.BIN = bin
        self.compile_times = 2
        self.halt_on_error = True
        self.output_dir = '.'

    def __call__(self, texfile, tex_args=''):
        if platform.system() == 'Windows':
            texfile = texfile.replace('\\', '/')
        cmd_bin = self.lookup_bin()
        cmd_args = []
        if self.halt_on_error:
            cmd_args.append('-halt-on-error')
        if self.output_dir:
            cmd_args.append('-output-directory=' + self.output_dir)
        if tex_args:
            cmd_args.append(tex_args)
        cmdline = cmd_bin + ' ' + ' '.join(cmd_args) + ' ' + texfile
        print('run command: ' + cmdline)
        log_path = os.path.join(self.output_dir, 'tex-compile.log')
        with open(log_path, 'wt', encoding='utf-8') as logfp:
            for idx in range(1, self.compile_times + 1):
                print('compile {} ({}/{})'.format(texfile, idx, self.compile_times))
                result = subprocess.run(cmdline, check=True, shell=True,
                                        stdout=None, stderr=logfp)
        print('compile finished')

    def lookup_bin(self):
        bin_path = None
        if platform.system() == 'Windows' and not self.BIN.endswith('.exe'):
            self.BIN += '.exe'
        if os.path.isfile(self.BIN):
            bin_path = self.BIN
        else:
            bin_path = lookup_file(self.BIN, self.PATH)
            print(bin_path)
        return bin_path


def render_template(texfile, config=None):
    default_config = None
    with open(texfile, 'rt', encoding='utf-8') as texfp:
        front_matter = tex_front_matter(texfp)
        default_config = yaml.load(front_matter)
        if config:
            update_mapping(config, default_config)
    tex_env = jinja2.Environment(
        block_start_string=r'\block{',
        block_end_string=r'}',
        variable_start_string=r'\var{',
        variable_end_string=r'}',
        comment_start_string='\#{',
        comment_end_string='}',
        line_statement_prefix='%%',
        line_comment_prefix='%#',
        trim_blocks=True,
        autoescape=False,
        loader=jinja2.FileSystemLoader(os.path.abspath('.'))
    )
    template = tex_env.get_template(texfile)
    content = template.render(default_config)
    return content


def gen_table(template_file, data, build_dir='build/tex', template_config=None):
    if not os.path.isdir(build_dir):
        os.makedirs(build_dir)
    if not isinstance(template_config, dict):
        template_config = {}
    # fix font config (due to strange behavior of XeLatex)
    font_conf = template_config.get('fonts', {})
    for k, v in font_conf.items():
        if v.endswith('.ttf'):
            basename = os.path.basename(v)
            target_font = os.path.join(build_dir, basename)
            if not os.path.exists(target_font):
                shutil.copy(v, target_font)
            font_conf[k] = basename
    update_mapping({'data': data}, template_config)
    content = render_template(template_file, template_config)

    orig_path = os.getcwd()
    os.chdir(build_dir)

    full_texfile = os.path.splitext(os.path.basename(template_file))[0] + '-full.tex'
    with open(full_texfile, 'wt', encoding='utf-8') as texfp:
        texfp.write(content)
    xelatex = XeLaTex()
    xelatex(full_texfile)

    os.chdir(orig_path)


if __name__ == '__main__':
    template_file = 'tex/simple-template.tex'
    data = None
    with open('data/zh-small.charset.json', 'rt', encoding='utf-8') as fp:
        data = json.loads(fp.read())
    gen_table(template_file, data, template_config={
        'title': '手写字符采集表',
        'comment': '请用黑色签字笔书写',
    })

