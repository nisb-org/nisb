export default {
  toolbar: {
    tab: 'Feed',
    tabTitle: 'Feed',
    expandLeftSidebar: 'Expand left sidebar',
    expandRightSidebar: 'Expand right sidebar'
  },

  panel: {
    tabs: {
      mine: {
        full: '📝 My Feed',
        noEmoji: 'My Feed',
        compact: 'Mine'
      },
      latest: {
        full: '🌐 Explore',
        noEmoji: 'Explore',
        compact: 'Explore'
      },
      tags: {
        full: '🏷️ Tags',
        noEmoji: 'Tags',
        compact: 'Tags'
      },
      foryou: {
        full: '✨ For You',
        noEmoji: 'For You',
        compact: 'For You'
      }
    },

    tag: {
      clear: 'Clear tag'
    },

    actions: {
      notifications: 'Notifications',
      me: 'Me',
      refresh: 'Refresh',
      loading: 'Loading…',
      menu: 'Menu'
    },

    drawer: {
      close: 'Close'
    },

    delete: {
      title: 'Delete this post?',
      desc: 'This action cannot be undone, and copies already cached by others cannot be removed.',
      cancel: 'Cancel',
      confirm: 'Delete'
    },

    toast: {
      refreshFailed: 'Refresh failed.',
      deleteFailed: 'Delete failed.',
      deleted: 'Deleted.'
    }
  },

  detail: {
    common: {
      busy: '...'
    },

    actions: {
      close: 'Close'
    },

    author: {
      avatarAlt: 'avatar'
    },

    follow: {
      follow: 'Follow',
      unfollow: 'Unfollow',
      compactFollow: 'F',
      compactUnfollow: 'UF'
    },

    bookmark: {
      bookmark: 'Bookmark',
      unbookmark: 'Unbookmark',
      compactBookmark: 'BM',
      compactUnbookmark: 'UBM'
    },

    status: {
      deleted: 'Retracted'
    },

    states: {
      loading: 'Loading…'
    },

    fallbacks: {
      untitled: 'Untitled',
      unknownAuthor: 'unknown'
    },

    errors: {
      toolFailed: 'Tool failed.',
      allToolCandidatesFailed: 'All tool candidates failed.',
      missingFeedId: 'Missing feed_id.'
    },

    toast: {
      followFailed: 'Follow failed.',
      bookmarkFailed: 'Bookmark failed.'
    }
  },

  comments: {
    title: 'Comments',

    actions: {
      refresh: 'Refresh',
      loading: 'Loading…',
      post: 'Post',
      posting: 'Posting…'
    },

    editor: {
      placeholder: 'Markdown'
    },

    states: {
      loading: 'Loading…',
      empty: 'No comments.'
    },

    errors: {
      toolFailed: 'Tool failed.',
      allToolCandidatesFailed: 'All tool candidates failed.'
    },

    toast: {
      loadFailed: 'Load comments failed.',
      postFailed: 'Post comment failed.',
      replyEmpty: 'Reply content is empty.',
      replyFailed: 'Reply failed.',
      deleteFailed: 'Delete comment failed.'
    }
  },

  commentNode: {
    author: {
      avatarAlt: 'avatar'
    },

    fallbacks: {
      unknownAuthor: 'unknown'
    },

    vote: {
      like: 'Like',
      downvote: 'Down',
      spam: 'Spam'
    },

    actions: {
      reply: 'Reply',
      delete: 'Delete',
      post: 'Post',
      posting: 'Posting…',
      cancel: 'Cancel'
    },

    editor: {
      replyPlaceholder: 'Reply (Markdown)'
    },

    status: {
      pending: 'Pending',
      failed: 'Failed',
      deleted: 'Deleted'
    },

    toast: {
      voteFailed: 'Vote failed.'
    }
  },

  tagsView: {
    title: 'Popular tags',

    actions: {
      refresh: 'Refresh',
      loading: 'Loading…'
    },

    states: {
      empty: 'No tags yet.'
    },

    toast: {
      loadFailed: 'Get tags failed.'
    }
  },

  timeline: {
    actions: {
      loadMore: 'Load more',
      loading: 'Loading…'
    },

    states: {
      empty: 'No posts yet.'
    },

    errors: {
      listFailed: 'Feed list failed.'
    },

    toast: {
      refreshFailed: 'Refresh failed.',
      loadMoreFailed: 'Load more failed.'
    }
  },

  itemCard: {
    author: {
      avatarAlt: 'avatar'
    },

    fallbacks: {
      untitled: 'Untitled',
      unknownAuthor: 'unknown',
      unknownSource: 'Unknown source'
    },

    vote: {
      like: 'Like',
      boost: 'Boost',
      downvote: 'Downvote (24h)',
      spam: 'Report spam (7d)'
    },

    bookmark: {
      bookmark: 'Bookmark',
      unbookmark: 'Unbookmark'
    },

    actions: {
      delete: 'Delete'
    },

    score: {
      title: 'Score: {score}',
      inline: '· Score: {score}'
    },

    toast: {
      voted: 'Voted.',
      voteFailed: 'Vote failed.',
      bookmarked: 'Bookmarked.',
      unbookmarked: 'Unbookmarked.',
      bookmarkFailed: 'Bookmark failed.'
    },

    state: {
      unread: 'Unread',
      read: 'Read'
    },

    signals: {
      comments: '{count} comments',
      notifications: '{count} notifications'
    }
  },

  notifications: {
    title: 'Notifications',

    actor: {
      avatarAlt: 'avatar',
      unknown: 'unknown'
    },

    actions: {
      markAllRead: 'Mark all read',
      markAllReadCompact: '✓✓',
      refresh: 'Refresh',
      refreshCompact: '↻',
      loading: 'Loading…',
      read: 'Read',
      markRead: 'Mark read'
    },

    states: {
      empty: 'No notifications yet.'
    },

    ref: {
      feed: 'Feed: {id}'
    },

    time: {
      minute: '{count}m',
      hour: '{count}h',
      day: '{count}d',
      week: '{count}w'
    },

    toast: {
      loadFailed: 'Load notifications failed.',
      markReadFailed: 'Mark read failed.',
      markAllReadFailed: 'Mark all read failed.'
    }
  },

  mePanel: {
    title: 'Me',
    subtitle: 'Your feed identity, saved items, and social graph.',

    tabs: {
      ariaLabel: 'Feed user panel tabs',
      profile: 'Profile',
      bookmarks: 'Bookmarks',
      following: 'Following',
      followers: 'Followers'
    },

    profile: {
      title: 'Feed identity',
      desc: 'This identity is shown in feed interactions.',
      hint: 'Your avatar, display name, and bio help other workspace users recognize your comments, votes, and bookmarks.'
    },

    bookmarks: {
      title: 'Saved feed items',
      desc: 'Open or remove items you have bookmarked.'
    },

    following: {
      title: 'Following',
      desc: 'People whose feed activity you follow.'
    },

    followers: {
      title: 'Followers',
      desc: 'People who follow your feed activity.'
    },

    labels: {
      userId: 'User ID',
      avatar: 'Avatar',
      displayName: 'Display name',
      bio: 'Bio'
    },

    placeholders: {
      displayName: 'Enter display name',
      bio: 'Write something about yourself',
      searchFollowing: 'Search following',
      searchFollowers: 'Search followers'
    },

    actions: {
      refresh: 'Refresh',
      loading: 'Loading...',
      save: 'Save',
      saving: 'Saving...',
      uploadAvatar: 'Upload avatar',
      uploading: 'Uploading...',
      clear: 'Clear',
      removeBookmark: 'Remove bookmark',
      unfollow: 'Unfollow',
      followBack: 'Follow back',
      working: 'Working...'
    },

    states: {
      noBookmarks: 'No bookmarks yet.',
      noFollowing: 'No following users.',
      noFollowers: 'No followers yet.'
    },

    avatar: {
      alt: 'Avatar',
      inputLabel: 'Choose avatar image'
    },

    fallbacks: {
      unknownUser: 'Unknown user',
      untitled: 'Untitled'
    },

    toast: {
      loadProfileFailed: 'Failed to load profile',
      refreshFailed: 'Refresh failed',
      saveFailed: 'Save failed',
      saved: 'Saved',
      bookmarkRemoved: 'Bookmark removed',
      removeBookmarkFailed: 'Failed to remove bookmark',
      unfollowFailed: 'Failed to unfollow',
      followFailed: 'Failed to follow',
      uploadFailed: 'Failed to upload avatar'
    }
  }
}
