import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, Send, Home, ChevronRight, ArrowLeft } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { inquiriesApi } from '../lib/api';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { Skeleton } from '../components/ui/Skeleton';
import { StatusBadge } from '../components/ui/Badge';
import { formatDateTime, getErrorMessage } from '../lib/utils';
import type { Inquiry, Message } from '../types';

export default function MessagesPage() {
  const { user } = useAuth();
  const { error: toastError } = useToast();
  const [selectedInquiry, setSelectedInquiry] = useState<Inquiry | null>(null);
  const [replyText, setReplyText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: inquiries, isLoading: loadingInquiries } = useQuery({
    queryKey: ['inquiries', 'me'],
    queryFn: inquiriesApi.getMyInquiries,
  });

  const { data: messages, isLoading: loadingMessages } = useQuery({
    queryKey: ['messages', selectedInquiry?.id],
    queryFn: () => inquiriesApi.getMessages(selectedInquiry!.id),
    enabled: !!selectedInquiry,
    refetchInterval: 5000, // poll every 5 seconds for new messages
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) => inquiriesApi.sendMessage(selectedInquiry!.id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages', selectedInquiry?.id] });
      setReplyText('');
    },
    onError: (err) => toastError('Failed to send', getErrorMessage(err)),
  });

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim()) return;
    sendMutation.mutate(replyText.trim());
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Messages</h1>
        <p className="text-slate-500 mt-1">Your property inquiry conversations</p>
      </div>

      <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="flex h-[600px]">
          {/* Inbox sidebar */}
          <div
            className={`w-full md:w-80 border-r border-slate-100 flex flex-col ${
              selectedInquiry ? 'hidden md:flex' : 'flex'
            }`}
          >
            <div className="p-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Inbox</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                {inquiries?.length ?? 0} conversation{inquiries?.length !== 1 ? 's' : ''}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingInquiries ? (
                <div className="p-4 space-y-4">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="space-y-2">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-full" />
                    </div>
                  ))}
                </div>
              ) : inquiries?.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center p-6">
                  <MessageSquare className="w-10 h-10 text-slate-300 mb-3" />
                  <p className="text-slate-500 text-sm font-medium">No messages yet</p>
                  <p className="text-slate-400 text-xs mt-1">Contact a seller to start</p>
                </div>
              ) : (
                <div>
                  {inquiries?.map((inq) => (
                    <InquiryItem
                      key={inq.id}
                      inquiry={inq}
                      isSelected={selectedInquiry?.id === inq.id}
                      onClick={() => setSelectedInquiry(inq)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Conversation */}
          <div
            className={`flex-1 flex flex-col ${
              !selectedInquiry ? 'hidden md:flex' : 'flex'
            }`}
          >
            {!selectedInquiry ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mb-4">
                  <MessageSquare className="w-8 h-8 text-slate-300" />
                </div>
                <h3 className="text-lg font-semibold text-slate-700 mb-1">Select a conversation</h3>
                <p className="text-slate-400 text-sm">Choose an inquiry from the sidebar to read and reply</p>
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-3">
                  <button
                    className="md:hidden p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-50"
                    onClick={() => setSelectedInquiry(null)}
                  >
                    <ArrowLeft className="w-5 h-5" />
                  </button>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-slate-900">
                        {selectedInquiry.listing?.title ?? `Listing #${selectedInquiry.listing_id}`}
                      </p>
                      <StatusBadge status={selectedInquiry.status} />
                    </div>
                    {selectedInquiry.listing && (
                      <Link
                        to={`/listings/${selectedInquiry.listing_id}`}
                        className="text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1 mt-0.5"
                      >
                        <Home className="w-3 h-3" />
                        View property
                        <ChevronRight className="w-3 h-3" />
                      </Link>
                    )}
                  </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-5 space-y-4">
                  {/* Original inquiry */}
                  <div className="flex justify-end">
                    <div className="max-w-xs lg:max-w-md">
                      <p className="text-xs text-slate-400 text-right mb-1">
                        {formatDateTime(selectedInquiry.created_at)} · You
                      </p>
                      <div className="bg-blue-500 text-white rounded-2xl rounded-tr-sm px-4 py-2.5">
                        <p className="text-sm leading-relaxed">{selectedInquiry.message}</p>
                      </div>
                    </div>
                  </div>

                  {/* Thread messages */}
                  {loadingMessages ? (
                    <div className="space-y-3">
                      <Skeleton className="h-12 w-48" />
                      <Skeleton className="h-12 w-56 ml-auto" />
                    </div>
                  ) : (
                    messages?.map((msg) => (
                      <MessageBubble
                        key={msg.id}
                        message={msg}
                        isMine={msg.sender_id === user?.id}
                      />
                    ))
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Reply form */}
                <form
                  onSubmit={handleSend}
                  className="px-4 py-4 border-t border-slate-100 flex items-end gap-3"
                >
                  <textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        if (replyText.trim()) handleSend(e);
                      }
                    }}
                    placeholder="Type a message... (Enter to send)"
                    rows={2}
                    className="flex-1 resize-none rounded-2xl border border-slate-300 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <Button
                    type="submit"
                    isLoading={sendMutation.isPending}
                    disabled={!replyText.trim()}
                    className="shrink-0 h-11 w-11 rounded-xl p-0 flex items-center justify-center"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function InquiryItem({
  inquiry,
  isSelected,
  onClick,
}: {
  inquiry: Inquiry;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3.5 border-b border-slate-50 transition-colors ${
        isSelected ? 'bg-blue-50' : 'hover:bg-slate-50'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <p className={`text-sm font-semibold line-clamp-1 ${isSelected ? 'text-blue-700' : 'text-slate-900'}`}>
          {inquiry.listing?.title ?? `Listing #${inquiry.listing_id}`}
        </p>
        <StatusBadge status={inquiry.status} />
      </div>
      <p className="text-xs text-slate-500 line-clamp-2">{inquiry.message}</p>
      <p className="text-xs text-slate-400 mt-1">{formatDateTime(inquiry.created_at)}</p>
    </button>
  );
}

function MessageBubble({
  message,
  isMine,
}: {
  message: Message;
  isMine: boolean;
}) {
  return (
    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'}`}>
      <div className="max-w-xs lg:max-w-md">
        <p className={`text-xs text-slate-400 mb-1 ${isMine ? 'text-right' : 'text-left'}`}>
          {formatDateTime(message.created_at)} · {isMine ? 'You' : 'Seller'}
        </p>
        <div
          className={`px-4 py-2.5 rounded-2xl ${
            isMine
              ? 'bg-blue-500 text-white rounded-tr-sm'
              : 'bg-slate-100 text-slate-900 rounded-tl-sm'
          }`}
        >
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    </div>
  );
}
