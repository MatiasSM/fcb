from fcb.framework.workflow.PipelineTask import PipelineTask


class SendingError(Exception):
    pass


class SenderTask(PipelineTask):

    # override from PipelineTask
    def process_data(self, block):
        """
        Note: Expects Compressor Block like objects
        """

        destinations = self.destinations()
        ''' FIXME currently we return block whether it was correctly processed or not because MailSenders are chained
            and not doing that would mean other wouldn't be able to try.'''
        if not set(destinations).issubset(block.destinations):
            self.log.debug("Block not for any of the associated destinations: %s", destinations)
        else:
            try:
                self.do_send(block)
                # mark the block as sent by this sender
                block.send_destinations.extend(destinations)

                verif_data = self.verification_data()
                if verif_data is not None:
                    for destination in destinations:
                        block.destinations_verif_data[destination] = verif_data
            except SendingError:
                self.log.exception("Failed to send block (%s) to destination (%s)", block, destinations)
        return block

    def destinations(self):
        raise NotImplementedError()

    def do_send(self, block):
        """
        Does the actual sending

        :param block: to send

        :raise: SendingError if sending fails
        """
        raise NotImplementedError()


    def verification_data(self):
        """
        :return: verification data (if any) or None if no-one (yet)
        """
        return None
