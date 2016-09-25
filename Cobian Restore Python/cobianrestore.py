#Core
import argparse, datetime, math, re, os, shutil
from pathlib import WindowsPath
#Dependencies
import progressbar, win_unicode_console
#Test
import time

class BackupFragment:
    def __init__(self, path, datetime):
        self.path = path
        self.datetime = datetime

class BackupFile:
    def __init__(self, relative, absolute):
        self.relative = relative
        self.absolute = absolute
        self.filesize = os.path.getsize(absolute)
        self.hits = 1

class LogFile:
    def __init__(self, path):
        self.path = path
    
    def open(self):
        self.file = open(str(self.path), "w")

    def log(self,string):
        print(string)
        self.file.write(string + "\n")
        self.file.flush()

    def logonly(self,string):
        self.file.write(string + "\n")
        self.file.flush()

    def close(self):
        self.file.close()

def convert_size(size):
   #From http://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python
    divisor = 1024
    if (size == 0):
       return '0B'
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size,divisor)))
    p = math.pow(divisor,i)
    s = round(size/p,2)
    return '%s %s' % (s,size_name[i])


def main():
    LONG_PATH_PREFIX = "\\\\?\\"
    win_unicode_console.enable()
    parser = argparse.ArgumentParser(description="A program to conflate and restore incremental backups created by Cobian Backup")
    parser.add_argument("source",help="The folder containing the Cobian Backups")
    parser.add_argument("destination",help="The folder to restore the backups to")
    parser.add_argument("-o","--overwrite",action="store_true",help="Overwrite existing files with the same name")
    parser.add_argument("-p","--nopermissions",action="store_true",help="Does not copy permission or metadata information from the source")
    parser.add_argument("-m","--nometadata",action="store_true",help="Does not copy metadata information from the source")
    #parser.parse_args(["-h"])
    #args = parser.parse_args(["E:","F:"])
    #args = parser.parse_args([r"E:\Cobian Backup\My Documents",r"E:\Write Restricted Test"])
    #args = parser.parse_args([r"E:\Cobian Backup\My Documents",r"E:\Write Restricted Test\New Folder"])
    args = parser.parse_args(["E:\Cobian Backup\My Documents","E:\Restore Test"])
    #args = parser.parse_args(["E:\Cobian Backup\My Documents","E:\Restore Test","-o"])
    #args = parser.parse_args()
    print(args)

    #Test directories
    if not args.source.startswith(LONG_PATH_PREFIX):
        args.source = LONG_PATH_PREFIX + args.source
    if not args.source.endswith("\\"):
        args.source = args.source + "\\"
    source = WindowsPath(args.source)
    try:
        if not source.is_dir():
            print("Source must be a valid directory.")
            return
    except WindowsError as winerror:
        print(winerror)
        print("Unable to access the source directory. Check the directory exists, and ensure you have permissions to access it.")
        return

    if not args.destination.startswith(LONG_PATH_PREFIX):
        args.destination = LONG_PATH_PREFIX + args.destination
    if not args.destination.endswith("\\"):
        args.destination = args.destination + "\\"
    destination = WindowsPath(args.destination)
    log = LogFile(WindowsPath(args.destination + "\\" + "cobianrestore.log"))
    try:
        if destination.exists():
            if not destination.is_dir():
                print("Destination must be a valid directory.")
                return
            else:
                try:
                    log.path.touch()
                except WindowsError as winerror:
                    print(winerror)
                    print("Unable to write to the destination directory. Ensure you have permissions to access it.")
                    return
        else:
            try:
                destination.mkdir(parents=True)
            except WindowsError as winerror:
                print(winerror)
                print("Unable to create the destination directory. Ensure you have permissions to access it.")
                return
    except WindowsError as winerror:
        print(winerror)
        print("Unable to access the destination directory. Ensure you have permissions to access it.")
        return
        
    log.open()
    log.logonly("---Starting logfile at {}---".format(datetime.datetime.now()))

    #Get fragments
    fragments = []
    fragment = re.compile(r"^(.*)(\d{4})-(\d{2})-(\d{2}) (\d{2});(\d{2});(\d{2})(.*)$")
    log.log("Analysing fragments...")
    for path in source.iterdir():
        try:
            if path.is_dir():
                m = fragment.match(path.parts[-1])
                if m:
                    parts = [int(x) for x in [m.group(i) for i in list(range(2,8))]]
                    fragments.append(BackupFragment(path, datetime.datetime(parts[0],parts[1],parts[2],parts[3],parts[4],parts[5])))
        except WindowsError as winerror:
            log.log(str(winerror))
            continue
    if len(fragments) == 0:
        log.log("No backup fragments found.\nPlease select a directory containing Cobian Backup fragments in the format <name> YYYY-MM-DD HH;MM;SS <backup type>")
        return
    else:
        fragments.sort(key=lambda x: x.datetime, reverse=True)
        log.log("{} fragments found between {} and {}".format(len(fragments),fragments[-1].datetime,fragments[0].datetime))
    
    
    #Create file list
    restore_files = {}
    restore_files_bytes = 0
    log.log("Analysing files...")
    for f in fragments:
        for root, dirs, files in os.walk(str(f.path)):
            relativepath = root[len(str(f.path)):]
            for file in files:
                filename = relativepath + "\\" + file
                if filename not in restore_files:
                    restore_files[filename] = BackupFile(filename, root + "\\" + file)
                    restore_files_bytes += restore_files[filename].filesize
                    #print("+ Adding {} to restore list".format(filename))
                else:
                    restore_files[filename].hits += 1
                    #print("x Existing file {} not added".format(filename))
            #print(relativepath,"->",root)
    #multiples = [file for file in restore_files.values() if file.hits > 1]
    #multiples.sort(key = lambda x: x.hits)
    #for file in multiples:
    #    #if "Eclipse Workspace" in file.relative or "Aptana Studio" in file.relative or "Visual Studio" in file.relative:
    #    #    pass
    #    if "TAFE" in file.relative:
    #        print(file.relative, file.hits)

    #Copy files
    overwrite_confirmation = args.overwrite
    log.logonly("Analysis found {:,} files totalling {}".format(len(restore_files),convert_size(restore_files_bytes)))
    files_restored = 0
    files_skipped = 0
    files_errored = 0
    if input("This operation will restore {:,} files totalling {}. Proceed? Y/N: ".format(len(restore_files),convert_size(restore_files_bytes))).upper() == "Y":
        bytes_bar = progressbar.ProgressBar(0,restore_files_bytes,[progressbar.Bar()," ",progressbar.ETA()," ",progressbar.AdaptiveTransferSpeed(samples=10)])
        total_bytes = 0
        restore_files_sorted = sorted(list(restore_files.values()), key = lambda x: x.relative)
        for file in restore_files_sorted:
            try:
                destfile = WindowsPath(args.destination + file.relative[1:])
                if not destfile.parents[0].exists():
                    destfile.parents[0].mkdir(parents=True)
                copy = False
                if not destfile.exists() or args.overwrite:
                    copy = True
                else:
                    if not overwrite_confirmation:
                        decision = input("\nDo you want to overwrite {}? [Y]es, [YA]Yes to all, [N]o, [NA]No to all: ".format(str(destfile))).upper()
                        if decision == "YA" or decision == "NA":
                            overwrite_confirmation = True
                        if decision == "YA":
                            args.overwrite = True
                        if decision == "NA":
                            args.overwrite = False
                        if decision == "Y" or decision == "YA":
                            copy = True

                if copy:
                    if args.nopermissions:
                        shutil.copyfile(file.absolute,str(destfile),follow_symlinks=False)
                    elif args.nometadata:
                        shutil.copy(file.absolute,str(destfile),follow_symlinks=False)
                    else:
                        shutil.copy2(file.absolute,str(destfile),follow_symlinks=False)
                    files_restored += 1
                else:
                    files_skipped += 1
            
                total_bytes += file.filesize
                bytes_bar.update(total_bytes)
            except WindowsError as winerror:
                files_errored += 1
                print("\n" + str(winerror))
                log.logonly(str(winerror))
                continue
        log.log("\n---Restore complete ({} files restored, {} files skipped, {} files errored).---".format(files_restored,files_skipped,files_errored))
        print("Check the log file at {} for additional information.".format(log.path))
    else:
        log.log("Operation cancelled by user.")

main()

