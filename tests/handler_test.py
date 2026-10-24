# Compile the actual Apache 2.x handler body against minimal httpd substitutes.
import os, subprocess, tempfile
from pathlib import Path
prefix='\n#include <cstring>\n#include <cassert>\n#include <stdexcept>\n#define UNLIKELY(x) (x)\n#define HANDLER_NAME "uploader"\n#define DECLINED -1\n#define HTTP_INTERNAL_SERVER_ERROR 500\nstruct request_rec {const char *handler; const char *path_info;};\nstruct ApacheResponse {};\nstatic int mode=0;\nstruct UploaderConfig {\n bool is_debug_mode=false;\n bool is_active(){return true;}\n void update_template(){}\n};\nstatic UploaderConfig config_instance;\nstatic bool ap_is_initial_req(request_rec*){return true;}\nstatic UploaderConfig *uploader_get_dir_config(request_rec*){return &config_instance;}\nstruct Logger {void error(const char*,int,request_rec*,const char*,const char*){}};\nstatic Logger logger;\ntemplate<class R> int uploader_command_handler(request_rec*,UploaderConfig*,const char*) {\n if(mode==1) throw "test";\n if(mode==2) throw std::runtime_error("test");\n return 200;\n}\n'
suffix='\nint main(){\n request_rec r={nullptr,"/"};assert(uploader_handler(&r)==DECLINED);\n r.handler="other";assert(uploader_handler(&r)==DECLINED);\n r.handler="uploader";assert(uploader_handler(&r)==200);\n mode=1;assert(uploader_handler(&r)==500);\n mode=2;assert(uploader_handler(&r)==500);\n}\n'
source=(Path(__file__).resolve().parents[1]/'src/mod_uploader.cpp').read_text(encoding='utf8')
a=source.rindex('static int uploader_handler(request_rec *r)')
b=source.index('\nstatic void uploader_register_hooks',a)
with tempfile.TemporaryDirectory() as d:
    cpp=Path(d)/'handler.cpp'
    exe=Path(d)/('handler.exe' if os.name=='nt' else 'handler')
    cpp.write_text(prefix+source[a:b]+suffix,encoding='utf8')
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++11','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('handler: 5 assertions passed (mock httpd; not a module build)')
