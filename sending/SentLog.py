from sqlalchemy.orm.exc import NoResultFound

from database.helpers import get_session
from database.schema import FilesContainer, FilesDestinations, Destination, UploadedFile, FileFragment, \
    FilesInContainers
from framework.PipelineTask import PipelineTask


class SentLog(PipelineTask):
    def __init__(self, sent_log):
        PipelineTask.__init__(self)
        self._session = None
        self._sent_log_file = open(sent_log, 'a')

    # override from PipelineTask
    def process_data(self, block):
        """expects Block from Compressor"""
        self._log_in_db(block)
        self._log_in_sent_log(block)
        self.log.info("Sent file %s containing files: %s",
                      block.processed_data_file_info.basename,
                      str([file_info.path for file_info in block.content_file_infos]))
        return block

    # override from PipelineTask
    def on_stopped(self):
        if self._sent_log_file:
            self._sent_log_file.close()
        if self._session:
            self._session.commit()
            self._session.close()

    # --- low visibility methods ------------------------------
    def _get_uploaded_file(self, file_info, fragment_count=0):
        """
        :param file_info: contains file information to save or query
        :param fragment_count: amount of fragments associated to the file
        :return: an UploadedFile associated to the file_info
        """
        try:
            return self._session.query(UploadedFile).filter(UploadedFile.sha1 == file_info.sha1).one()
        except NoResultFound:
            new_instance = UploadedFile(
                sha1=file_info.sha1,
                file_name=file_info.path,
                fragment_count=fragment_count
            )
            self._session.add(new_instance)
            return new_instance

    def _log_in_db(self, block):
        if not self._session:
            self._session = get_session()

        sent_file_info = block.ciphered_file_info if hasattr(block, 'ciphered_file_info') \
            else block.processed_data_file_info

        # a new container has been saved
        file_container = FilesContainer(
            sha1=sent_file_info.sha1,
            file_name=sent_file_info.basename,
            encryption_key=block.cipher_key if hasattr(block, 'cipher_key') else '',
            container_size=sent_file_info.size
        )
        self._session.add(file_container)
        # FIXME we need the container id because file_destination is not getting it (not working example of SQLAlchemy)
        self._session.flush()  # get container id

        # associate destinations to the container
        for destination in block.send_destinations if hasattr(block, 'send_destinations') else []:
            file_destination = FilesDestinations()
            file_destination.destination = Destination.get_or_add(self._session, destination)
            file_destination.file_containers_id = file_container.id  # FIXME according to the example in SQLAlchemy, this shouldn't be needed
            file_container.files_destinations.append(file_destination)

        # save/update each file in the container
        for file_info in block.content_file_infos:
            uploaded_file_fragment_number = 0
            if hasattr(file_info, 'fragment_info'):  # check if it is a fragment
                uploaded_file_fragment_number = file_info.fragment_info.fragment_num
                uploaded_file = \
                    self._get_uploaded_file(file_info.fragment_info.file_info, file_info.fragment_info.fragments_count)

                # save a new fragment for the file
                file_fragment = FileFragment(
                    fragment_sha1=file_info.sha1,
                    fragment_name=file_info.path,
                    fragment_number=file_info.fragment_info.fragment_num
                )
                uploaded_file.fragments.append(file_fragment)
            else:  # not fragmented file
                uploaded_file = self._get_uploaded_file(file_info)

            self._session.flush()  # if uploaded_file has no id, we need one

            file_in_container_assoc = FilesInContainers(
                uploaded_file_fragment_number=uploaded_file_fragment_number,
                uploaded_files_id=uploaded_file.id
            )
            file_in_container_assoc.container_file = file_container
            file_container.fragments.append(file_in_container_assoc)

        self._session.commit()

    def _log_in_sent_log(self, block):
        """ Logs:
                block file | bfile (not encrypted) sha1 [| bfile encryption key | encrypted bfile sha1]
                <tab>content file | cfile sha1 | part of parts [| whole file sha1]
        """
        # FIXME all these should be done by the block itself
        self._sent_log_file.write("\n")
        sent_file_info = block.ciphered_file_info if hasattr(block, 'ciphered_file_info') \
            else block.processed_data_file_info
        self._sent_log_file.write("|".join((sent_file_info.basename, sent_file_info.sha1)))
        if hasattr(block, 'cipher_key'):
            self._sent_log_file.write("|")
            self._sent_log_file.write("|".join((block.cipher_key, block.ciphered_file_info.sha1)))
        for file_info in block.content_file_infos:
            self._sent_log_file.write("\n\t")
            self._sent_log_file.write("|".join((file_info.path, file_info.sha1)))
            if hasattr(file_info, 'fragment_info'):  # check if it is a fragment
                self._sent_log_file.write("|")
                self._sent_log_file.write("|".join((
                    "%d of %d" % (file_info.fragment_info.fragment_num, file_info.fragment_info.fragments_count),
                    file_info.fragment_info.file_info.sha1)))
